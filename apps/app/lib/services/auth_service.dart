import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;

import '../config/app_config.dart';

/// R46 — Flutter 端账户体系
///
/// 邮箱/密码注册登录 + JWT(7 天)+ flutter_secure_storage(iOS Keychain / Android Keystore)
///
/// 后端:
///   POST /api/auth/register {email, password, display_name?}
///   POST /api/auth/login    {email, password}
///   POST /api/auth/google   {id_token}     (R48 — 需 google_sign_in 包)
///   GET  /api/auth/me       (Bearer token)
///
/// token 存到 secure storage,启动时 hydrate。
/// 401 时清 token + 通知 UI 跳登录页(由 api_client 拦截器调 logout 并 push LoginPage)。
class AuthService extends ChangeNotifier {
  AuthService._();
  static final AuthService instance = AuthService._();

  static const _tokenKey = 'helix_auth_token';
  static const _userKey = 'helix_auth_user';

  final _storage = const FlutterSecureStorage();

  String? _token;
  Map<String, dynamic>? _user;

  String? get token => _token;
  Map<String, dynamic>? get user => _user;
  bool get isLoggedIn => _token != null && _token!.isNotEmpty;
  String? get email => _user?['email'] as String?;
  String? get displayName => _user?['display_name'] as String?;
  String? get userId => _user?['id'] as String? ?? _user?['user_id'] as String?;

  /// 启动时调用,读 token + user 进内存
  Future<void> hydrate() async {
    try {
      _token = await _storage.read(key: _tokenKey);
      final raw = await _storage.read(key: _userKey);
      if (raw != null && raw.isNotEmpty) {
        _user = jsonDecode(raw) as Map<String, dynamic>;
      }
      notifyListeners();
    } catch (e) {
      debugPrint('[AuthService] hydrate fail: $e');
    }
  }

  Future<AuthResult> register(
    String email,
    String password, {
    String? displayName,
  }) async {
    return _post('/api/auth/register', {
      'email': email.trim().toLowerCase(),
      'password': password,
      if (displayName != null && displayName.isNotEmpty) 'display_name': displayName,
    });
  }

  Future<AuthResult> login(String email, String password) async {
    return _post('/api/auth/login', {
      'email': email.trim().toLowerCase(),
      'password': password,
    });
  }

  Future<AuthResult> loginWithGoogleIdToken(String idToken) async {
    return _post('/api/auth/google', {'id_token': idToken});
  }

  /// R47 P3 — 触发 Google Sign-In 原生 flow + 自动 POST /api/auth/google
  ///
  /// iOS:用 Info.plist 里 GIDClientID(iOS OAuth client)弹原生选账号弹窗
  /// 拿到 idToken → 后端 verify(audience 已加 iOS client ID 白名单)→ 签 JWT
  Future<AuthResult> loginWithGoogle() async {
    try {
      // serverClientId = Web OAuth client ID(让 Google 同时签一份 aud=web 的 token,
      // 后端可一并接受;iOS 自己的 client ID 由 Info.plist GIDClientID 指定)
      const webServerClientId =
          '151316463137-0gm4d85uc77fthd4lgcvrdvvn6jhdi3t.apps.googleusercontent.com';
      final googleSignIn = GoogleSignIn(
        scopes: const ['email', 'profile', 'openid'],
        serverClientId: webServerClientId,
      );
      final account = await googleSignIn.signIn();
      if (account == null) {
        return AuthResult.fail('用户取消 Google 登录');
      }
      final auth = await account.authentication;
      final idToken = auth.idToken;
      if (idToken == null || idToken.isEmpty) {
        return AuthResult.fail('Google 未返回 ID token,请重试');
      }
      return await loginWithGoogleIdToken(idToken);
    } catch (e) {
      return AuthResult.fail('Google 登录失败: ${e.toString().substring(0, e.toString().length > 100 ? 100 : e.toString().length)}');
    }
  }

  Future<AuthResult> _post(String path, Map<String, dynamic> body) async {
    try {
      final resp = await http
          .post(
            Uri.parse('${AppConfig.backendBaseUrl}$path'),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode(body),
          )
          .timeout(const Duration(seconds: 15));
      final data = jsonDecode(resp.body) as Map<String, dynamic>;
      if (resp.statusCode == 200 && data['success'] == true && data['token'] != null) {
        await _persist(data['token'] as String, data);
        return AuthResult.ok(data);
      }
      return AuthResult.fail(
        (data['error'] ?? data['detail'] ?? '请求失败').toString(),
      );
    } catch (e) {
      return AuthResult.fail('网络错误: ${e.toString().substring(0, e.toString().length > 80 ? 80 : e.toString().length)}');
    }
  }

  Future<void> _persist(String token, Map<String, dynamic> userData) async {
    _token = token;
    // 把 user 字段(去掉 token / success)存到 _user
    _user = {
      'id': userData['user_id'],
      'email': userData['email'],
      'display_name': userData['display_name'],
    };
    await _storage.write(key: _tokenKey, value: token);
    await _storage.write(key: _userKey, value: jsonEncode(_user));
    notifyListeners();
  }

  /// 验证当前 token 是否有效
  Future<bool> validateToken() async {
    if (_token == null) return false;
    try {
      final resp = await http
          .get(
            Uri.parse('${AppConfig.backendBaseUrl}/api/auth/me'),
            headers: {'Authorization': 'Bearer $_token'},
          )
          .timeout(const Duration(seconds: 8));
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        _user = data;
        await _storage.write(key: _userKey, value: jsonEncode(_user));
        notifyListeners();
        return true;
      }
      if (resp.statusCode == 401) {
        await logout();
      }
      return false;
    } catch (e) {
      debugPrint('[AuthService] validateToken fail: $e');
      return _token != null; // 网络错误就当 token 有效(避免离线踢人)
    }
  }

  Future<void> logout() async {
    _token = null;
    _user = null;
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _userKey);
    notifyListeners();
  }
}

class AuthResult {
  final bool success;
  final String? error;
  final Map<String, dynamic>? data;
  AuthResult.ok(this.data) : success = true, error = null;
  AuthResult.fail(this.error) : success = false, data = null;
}
