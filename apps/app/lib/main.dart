import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:firebase_core/firebase_core.dart';
import 'app.dart';
import 'providers/locale_provider.dart';
import 'services/wallet_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // 锁定竖屏
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // 加载用户语言偏好
  await localeProvider.load();

  // 初始化钱包服务
  await WalletService.instance.init();

  // 初始化 Firebase（不自动请求推送权限，等用户手动开启）
  try {
    await Firebase.initializeApp();
    // 注意：不再调用 PushNotificationService.initialize()
    // 推送权限在用户手动开启通知开关时才请求（Apple 审核要求 4.5.4）
    debugPrint('Firebase initialized (push permission deferred to user action)');
  } catch (e) {
    debugPrint('Firebase init skipped (config missing?): $e');
  }

  // 捕获详细错误信息
  FlutterError.onError = (details) {
    FlutterError.presentError(details);
    debugPrint('FLUTTER ERROR: ${details.exception}');
    debugPrint('${details.stack}');
  };

  runApp(const PumpSignalApp());
}
