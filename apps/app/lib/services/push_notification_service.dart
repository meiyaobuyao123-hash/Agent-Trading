import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:http/http.dart' as http;
// Supabase SDK removed — auth token no longer used
import 'deep_link_router.dart';

/// 后台消息处理（必须是顶层函数）
@pragma('vm:entry-point')
Future<void> _firebaseBackgroundHandler(RemoteMessage message) async {
  debugPrint('[Push] Background message: ${message.messageId}');
}

/// FCM/APNs 推送通知服务
///
/// 功能：
/// - 请求推送权限
/// - 获取 FCM Token 并上传后端
/// - 前台消息通过 flutter_local_notifications 显示
/// - 后台/点击消息处理
///
/// 使用：在 main.dart 中 Firebase.initializeApp() 之后调用
///   await PushNotificationService.initialize();
class PushNotificationService {
  PushNotificationService._();

  static final _messaging = FirebaseMessaging.instance;
  static final _localNotifications = FlutterLocalNotificationsPlugin();

  // 后端 API 地址（使用 AppConfig 统一配置）
  static String get _apiBase {
    try {
      return const String.fromEnvironment('BACKEND_URL', defaultValue: 'http://localhost:8000');
    } catch (_) {
      return 'http://localhost:8000';
    }
  }

  /// Android 通知渠道
  static const _androidChannel = AndroidNotificationChannel(
    'agent_trading_alerts',
    'Agent Trading Alerts',
    description: 'Strategy triggers and trade alerts',
    importance: Importance.high,
  );

  /// 是否已初始化
  static bool _initialized = false;

  /// 初始化推送服务
  ///
  /// 在 Firebase.initializeApp() 之后调用。
  /// 缺少 Firebase 配置时 graceful fallback，不会崩溃。
  static Future<void> initialize() async {
    if (_initialized) return;

    try {
      // 注册后台消息处理
      FirebaseMessaging.onBackgroundMessage(_firebaseBackgroundHandler);

      // 请求推送权限（iOS 需要用户授权）
      final settings = await _messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );

      if (settings.authorizationStatus == AuthorizationStatus.denied) {
        debugPrint('[Push] Permission denied by user');
        return;
      }

      debugPrint(
        '[Push] Permission granted: ${settings.authorizationStatus}',
      );

      // 初始化本地通知插件（前台显示用）
      await _initLocalNotifications();

      // 获取 FCM Token 并上传
      final token = await _messaging.getToken();
      if (token != null) {
        debugPrint('[Push] FCM Token obtained (${token.substring(0, 20)}...)');
        await _registerToken(token);
      }

      // 监听 Token 刷新
      _messaging.onTokenRefresh.listen((newToken) {
        debugPrint('[Push] Token refreshed');
        _registerToken(newToken);
      });

      // 前台消息处理
      FirebaseMessaging.onMessage.listen(_handleForegroundMessage);

      // 后台点击通知 → 打开 App
      FirebaseMessaging.onMessageOpenedApp.listen(_handleMessageOpenedApp);

      // 检查 App 是否从通知冷启动
      final initialMessage = await _messaging.getInitialMessage();
      if (initialMessage != null) {
        _handleMessageOpenedApp(initialMessage);
      }

      _initialized = true;
      debugPrint('[Push] Push notification service initialized');
    } catch (e) {
      // Firebase 未配置或其他错误 → 优雅降级
      debugPrint('[Push] Initialization failed (Firebase not configured?): $e');
    }
  }

  /// 初始化本地通知（Android 前台显示 + iOS badge）
  static Future<void> _initLocalNotifications() async {
    const androidSettings = AndroidInitializationSettings(
      '@mipmap/ic_launcher',
    );
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: false, // 已通过 FCM 请求
      requestBadgePermission: false,
      requestSoundPermission: false,
    );

    await _localNotifications.initialize(
      const InitializationSettings(
        android: androidSettings,
        iOS: iosSettings,
      ),
      onDidReceiveNotificationResponse: _onNotificationTapped,
    );

    // Android: 创建高优先级通知渠道
    if (Platform.isAndroid) {
      await _localNotifications
          .resolvePlatformSpecificImplementation<
              AndroidFlutterLocalNotificationsPlugin>()
          ?.createNotificationChannel(_androidChannel);
    }
  }

  /// 上传 FCM Token 到后端
  static Future<void> _registerToken(String token) async {
    final platform = Platform.isIOS ? 'ios' : 'android';

    try {
      final resp = await http.post(
        Uri.parse('$_apiBase/api/device/register'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'token': token,
          'platform': platform,
        }),
      );

      if (resp.statusCode == 200) {
        debugPrint('[Push] Token registered to backend');
      } else {
        debugPrint('[Push] Token registration failed: ${resp.statusCode}');
      }
    } catch (e) {
      debugPrint('[Push] Token registration error: $e');
    }
  }

  /// 处理前台消息 → 显示本地通知
  static void _handleForegroundMessage(RemoteMessage message) {
    debugPrint('[Push] Foreground message: ${message.notification?.title}');

    final notification = message.notification;
    if (notification == null) return;

    _localNotifications.show(
      notification.hashCode,
      notification.title,
      notification.body,
      NotificationDetails(
        android: AndroidNotificationDetails(
          _androidChannel.id,
          _androidChannel.name,
          channelDescription: _androidChannel.description,
          importance: Importance.high,
          priority: Priority.high,
          icon: '@mipmap/ic_launcher',
        ),
        iOS: const DarwinNotificationDetails(
          presentAlert: true,
          presentBadge: true,
          presentSound: true,
        ),
      ),
      payload: jsonEncode(message.data),
    );
  }

  /// 后台点击通知 → 导航到对应页面
  static void _handleMessageOpenedApp(RemoteMessage message) {
    debugPrint('[Push] Message opened app: ${message.data}');
    DeepLinkRouter.handleFromPushData(message.data);
  }

  /// 点击本地通知回调
  static void _onNotificationTapped(NotificationResponse response) {
    debugPrint('[Push] Notification tapped: ${response.payload}');

    if (response.payload != null) {
      try {
        final data = jsonDecode(response.payload!) as Map<String, dynamic>;
        DeepLinkRouter.handleFromPushData(data);
      } catch (_) {}
    }
  }

  /// 注销推送（用户登出时调用）
  static Future<void> unregister() async {
    try {
      final token = await _messaging.getToken();
      if (token == null) return;

      await http.delete(
        Uri.parse('$_apiBase/api/device/unregister'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode({'token': token}),
      );

      debugPrint('[Push] Token unregistered');
    } catch (e) {
      debugPrint('[Push] Unregister error: $e');
    }
  }

  /// 重新注册 Token（用户登录后调用）
  static Future<void> reRegister() async {
    try {
      final token = await _messaging.getToken();
      if (token != null) {
        await _registerToken(token);
      }
    } catch (e) {
      debugPrint('[Push] Re-register error: $e');
    }
  }
}
