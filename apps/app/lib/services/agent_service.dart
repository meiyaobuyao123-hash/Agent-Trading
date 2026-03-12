import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';

/// Agent API 服务 — 对接后端 FastAPI
class AgentService {
  static final AgentService instance = AgentService._();
  AgentService._();

  final _client = http.Client();

  // TODO: 生产环境替换为实际部署地址
  static const _apiBase = 'http://localhost:8000';
  static const _timeout = Duration(seconds: 30);

  String? get _token =>
      Supabase.instance.client.auth.currentSession?.accessToken;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Bearer $_token',
      };

  /// 解析后端错误信息
  String _parseError(http.Response resp) {
    try {
      final body = jsonDecode(resp.body) as Map<String, dynamic>;
      return body['detail'] as String? ?? '服务器错误 (${resp.statusCode})';
    } catch (_) {
      return '服务器错误 (${resp.statusCode})';
    }
  }

  // ═══════════════════════════════════════════════════════
  // 对话
  // ═══════════════════════════════════════════════════════

  /// 发送对话消息，失败时抛 AgentException
  Future<ChatResponse> chat(String message,
      {Map<String, dynamic>? context}) async {
    try {
      final resp = await _client
          .post(
            Uri.parse('$_apiBase/api/agent/chat'),
            headers: _headers,
            body: jsonEncode({
              'message': message,
              if (context != null) 'context': context,
            }),
          )
          .timeout(_timeout);

      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        return ChatResponse.fromJson(data);
      }
      throw AgentException(_parseError(resp));
    } on AgentException {
      rethrow;
    } catch (e) {
      throw AgentException('网络连接失败，请检查后端服务是否启动');
    }
  }

  // ═══════════════════════════════════════════════════════
  // 策略 CRUD
  // ═══════════════════════════════════════════════════════

  Future<List<AgentStrategy>> listStrategies({String? status}) async {
    try {
      var url = '$_apiBase/api/agent/strategies';
      if (status != null) url += '?status=$status';

      final resp = await _client
          .get(Uri.parse(url), headers: _headers)
          .timeout(_timeout);

      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final list = data['strategies'] as List<dynamic>? ?? [];
        return list
            .map((e) => AgentStrategy.fromJson(e as Map<String, dynamic>))
            .toList();
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  /// 创建策略 — 失败时抛 AgentException（含具体错误信息）
  Future<AgentStrategy> createStrategy(
    Map<String, dynamic> spec, {
    String? sourcePrompt,
  }) async {
    try {
      final resp = await _client
          .post(
            Uri.parse('$_apiBase/api/agent/strategies'),
            headers: _headers,
            body: jsonEncode({
              'spec': spec,
              if (sourcePrompt != null) 'source_prompt': sourcePrompt,
            }),
          )
          .timeout(_timeout);

      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final s = data['strategy'] as Map<String, dynamic>?;
        if (s != null) return AgentStrategy.fromJson(s);
        throw AgentException('返回数据格式异常');
      }
      throw AgentException(_parseError(resp));
    } on AgentException {
      rethrow;
    } catch (e) {
      throw AgentException('网络错误: $e');
    }
  }

  Future<bool> updateStrategyStatus(String id, String status) async {
    try {
      final resp = await _client
          .patch(
            Uri.parse('$_apiBase/api/agent/strategies/$id'),
            headers: _headers,
            body: jsonEncode({'status': status}),
          )
          .timeout(_timeout);
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<bool> deleteStrategy(String id) async {
    try {
      final resp = await _client
          .delete(
            Uri.parse('$_apiBase/api/agent/strategies/$id'),
            headers: _headers,
          )
          .timeout(_timeout);
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ═══════════════════════════════════════════════════════
  // 告警
  // ═══════════════════════════════════════════════════════

  Future<AlertsResponse?> listAlerts({
    int limit = 50,
    bool unreadOnly = false,
  }) async {
    try {
      final resp = await _client
          .get(
            Uri.parse(
                '$_apiBase/api/agent/alerts?limit=$limit&unread_only=$unreadOnly'),
            headers: _headers,
          )
          .timeout(_timeout);

      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        return AlertsResponse.fromJson(data);
      }
      return null;
    } catch (_) {
      return null;
    }
  }

  Future<bool> markAlertRead(String alertId) async {
    try {
      final resp = await _client
          .patch(
            Uri.parse('$_apiBase/api/agent/alerts/$alertId/read'),
            headers: _headers,
          )
          .timeout(_timeout);
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<int> getUnreadCount() async {
    try {
      final resp = await _client
          .get(
            Uri.parse('$_apiBase/api/agent/alerts/unread-count'),
            headers: _headers,
          )
          .timeout(_timeout);

      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        return data['unread_count'] as int? ?? 0;
      }
      return 0;
    } catch (_) {
      return 0;
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 异常类型
// ═══════════════════════════════════════════════════════════

class AgentException implements Exception {
  final String message;
  const AgentException(this.message);
  @override
  String toString() => message;
}

// ═══════════════════════════════════════════════════════════
// 数据模型
// ═══════════════════════════════════════════════════════════

class ChatResponse {
  final Map<String, dynamic>? strategy;
  final String message;
  final bool requiresConfirmation;

  const ChatResponse({
    this.strategy,
    required this.message,
    this.requiresConfirmation = false,
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) => ChatResponse(
        strategy: json['strategy'] as Map<String, dynamic>?,
        message: json['message'] as String? ?? '',
        requiresConfirmation: json['requires_confirmation'] as bool? ?? false,
      );
}

class AgentStrategy {
  final String id;
  final String name;
  final String? description;
  final Map<String, dynamic> conditions;
  final List<dynamic> actions;
  final Map<String, dynamic> filters;
  final List<String> dataSources;
  final int cooldownMin;
  final String status;
  final int triggerCount;
  final String? lastTriggered;
  final String? sourcePrompt;
  final String createdAt;

  const AgentStrategy({
    required this.id,
    required this.name,
    this.description,
    required this.conditions,
    required this.actions,
    required this.filters,
    required this.dataSources,
    required this.cooldownMin,
    required this.status,
    required this.triggerCount,
    this.lastTriggered,
    this.sourcePrompt,
    required this.createdAt,
  });

  factory AgentStrategy.fromJson(Map<String, dynamic> json) => AgentStrategy(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '未命名',
        description: json['description'] as String?,
        conditions: json['conditions'] as Map<String, dynamic>? ?? {},
        actions: json['actions'] as List<dynamic>? ?? [],
        filters: json['filters'] as Map<String, dynamic>? ?? {},
        dataSources: (json['data_sources'] as List<dynamic>?)
                ?.map((e) => e.toString())
                .toList() ??
            [],
        cooldownMin: json['cooldown_min'] as int? ?? 30,
        status: json['status'] as String? ?? 'active',
        triggerCount: json['trigger_count'] as int? ?? 0,
        lastTriggered: json['last_triggered'] as String?,
        sourcePrompt: json['source_prompt'] as String?,
        createdAt: json['created_at'] as String? ?? '',
      );

  bool get isActive => status == 'active';
  bool get isPaused => status == 'paused';
}

class AgentAlert {
  final String id;
  final String? strategyId;
  final String title;
  final String message;
  final String severity;
  final bool isRead;
  final String? tokenName;
  final String? chain;
  final String? tokenAddress;
  final Map<String, dynamic> triggerContext;
  final String createdAt;

  const AgentAlert({
    required this.id,
    this.strategyId,
    required this.title,
    required this.message,
    required this.severity,
    required this.isRead,
    this.tokenName,
    this.chain,
    this.tokenAddress,
    required this.triggerContext,
    required this.createdAt,
  });

  factory AgentAlert.fromJson(Map<String, dynamic> json) => AgentAlert(
        id: json['id'] as String? ?? '',
        strategyId: json['strategy_id'] as String?,
        title: json['title'] as String? ?? '',
        message: json['message'] as String? ?? '',
        severity: json['severity'] as String? ?? 'info',
        isRead: json['is_read'] as bool? ?? false,
        tokenName: json['token_name'] as String?,
        chain: json['chain'] as String?,
        tokenAddress: json['token_address'] as String?,
        triggerContext: json['trigger_context'] as Map<String, dynamic>? ?? {},
        createdAt: json['created_at'] as String? ?? '',
      );
}

class AlertsResponse {
  final List<AgentAlert> alerts;
  final int total;
  final int unreadCount;

  const AlertsResponse({
    required this.alerts,
    required this.total,
    required this.unreadCount,
  });

  factory AlertsResponse.fromJson(Map<String, dynamic> json) =>
      AlertsResponse(
        alerts: (json['alerts'] as List<dynamic>? ?? [])
            .map((e) => AgentAlert.fromJson(e as Map<String, dynamic>))
            .toList(),
        total: json['total'] as int? ?? 0,
        unreadCount: json['unread_count'] as int? ?? 0,
      );
}
