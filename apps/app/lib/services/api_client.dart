import 'dart:convert';
import 'package:http/http.dart' as http;

import 'auth_service.dart';

/// 通用 HTTP 客户端封装
///
/// R46:自动 attach Bearer token(从 AuthService 拿)
///       401 时清 token(AuthService notifyListeners → DisclaimerGate 自动跳登录页)
class ApiClient {
  static final ApiClient instance = ApiClient._();
  ApiClient._();

  final _client = http.Client();
  static const _timeout = Duration(seconds: 12);

  Map<String, String> _withAuth(Map<String, String>? extra) {
    final m = <String, String>{};
    if (extra != null) m.addAll(extra);
    final token = AuthService.instance.token;
    if (token != null && token.isNotEmpty) {
      m['Authorization'] = 'Bearer $token';
    }
    return m;
  }

  Future<Map<String, dynamic>?> get(
    String url, {
    Map<String, String>? headers,
  }) async {
    try {
      final resp = await _client
          .get(Uri.parse(url), headers: _withAuth(headers))
          .timeout(_timeout);
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
      if (resp.statusCode == 401) {
        await AuthService.instance.logout();
      }
      return null;
    } catch (_) {
      return null;
    }
  }

  Future<Map<String, dynamic>?> post(
    String url, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
  }) async {
    try {
      final resp = await _client
          .post(
            Uri.parse(url),
            headers: _withAuth({
              'Content-Type': 'application/json',
              ...?headers,
            }),
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(_timeout);
      if (resp.statusCode >= 200 && resp.statusCode < 300) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
      if (resp.statusCode == 401) {
        await AuthService.instance.logout();
      }
      return null;
    } catch (_) {
      return null;
    }
  }
}
