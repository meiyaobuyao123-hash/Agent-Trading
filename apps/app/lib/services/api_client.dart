import 'dart:convert';
import 'package:http/http.dart' as http;

/// 通用 HTTP 客户端封装
class ApiClient {
  static final ApiClient instance = ApiClient._();
  ApiClient._();

  final _client = http.Client();
  static const _timeout = Duration(seconds: 12);

  Future<Map<String, dynamic>?> get(
    String url, {
    Map<String, String>? headers,
  }) async {
    try {
      final resp = await _client
          .get(Uri.parse(url), headers: headers)
          .timeout(_timeout);
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
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
            headers: {
              'Content-Type': 'application/json',
              ...?headers,
            },
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(_timeout);
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
      return null;
    } catch (_) {
      return null;
    }
  }
}
