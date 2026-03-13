import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';
import '../config/app_config.dart';

/// Agent API 服务 — 对接后端 FastAPI
class AgentService {
  static final AgentService instance = AgentService._();
  AgentService._();

  final _client = http.Client();

  static const _apiBase = AppConfig.backendBaseUrl;
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
  // 交易记录
  // ═══════════════════════════════════════════════════════

  Future<ExecutionsResponse?> listExecutions(
    String strategyId, {
    int limit = 100,
  }) async {
    try {
      final resp = await _client
          .get(
            Uri.parse(
                '$_apiBase/api/agent/executions/$strategyId?limit=$limit'),
            headers: _headers,
          )
          .timeout(_timeout);

      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        return ExecutionsResponse.fromJson(data);
      }
      return null;
    } catch (_) {
      return null;
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

// ═══════════════════════════════════════════════════════════
// 交易记录模型
// ═══════════════════════════════════════════════════════════

class AgentExecution {
  final String id;
  final String? strategyId;
  final String? chain;
  final String? tokenAddress;
  final String action; // buy / sell
  final double amountUsd;
  final double amountToken;
  final String status; // pending / submitted / confirmed / failed
  final String? txHash;
  final double executedPrice;
  final double slippagePct;
  final double gasFeeUsd;
  final String? errorMessage;
  final String createdAt;
  final String? confirmedAt;

  const AgentExecution({
    required this.id,
    this.strategyId,
    this.chain,
    this.tokenAddress,
    required this.action,
    this.amountUsd = 0,
    this.amountToken = 0,
    required this.status,
    this.txHash,
    this.executedPrice = 0,
    this.slippagePct = 0,
    this.gasFeeUsd = 0,
    this.errorMessage,
    required this.createdAt,
    this.confirmedAt,
  });

  factory AgentExecution.fromJson(Map<String, dynamic> json) =>
      AgentExecution(
        id: json['id'] as String? ?? '',
        strategyId: json['strategy_id'] as String?,
        chain: json['chain'] as String?,
        tokenAddress: json['token_address'] as String?,
        action: json['action'] as String? ?? 'buy',
        amountUsd: (json['amount_usd'] as num?)?.toDouble() ?? 0,
        amountToken: (json['amount_token'] as num?)?.toDouble() ?? 0,
        status: json['status'] as String? ?? 'pending',
        txHash: json['tx_hash'] as String?,
        executedPrice: (json['executed_price'] as num?)?.toDouble() ?? 0,
        slippagePct: (json['slippage_pct'] as num?)?.toDouble() ?? 0,
        gasFeeUsd: (json['gas_fee_usd'] as num?)?.toDouble() ?? 0,
        errorMessage: json['error_message'] as String?,
        createdAt: json['created_at'] as String? ?? '',
        confirmedAt: json['confirmed_at'] as String?,
      );

  bool get isBuy => action == 'buy';
  bool get isConfirmed => status == 'confirmed';
  bool get isFailed => status == 'failed';

  String get chainLabel => switch (chain) {
    'solana' => 'SOL',
    'bsc' => 'BSC',
    'base' => 'BASE',
    'eth' => 'ETH',
    _ => chain?.toUpperCase() ?? '',
  };

  String get statusLabel => switch (status) {
    'confirmed' => '已确认',
    'failed' => '失败',
    'submitted' => '提交中',
    'pending' => '等待中',
    _ => status,
  };

  String get timeAgo {
    if (createdAt.isEmpty) return '';
    try {
      final dt = DateTime.parse(createdAt);
      final diff = DateTime.now().toUtc().difference(dt);
      if (diff.inMinutes < 1) return '刚刚';
      if (diff.inMinutes < 60) return '${diff.inMinutes}m前';
      if (diff.inHours < 24) return '${diff.inHours}h前';
      return '${diff.inDays}d前';
    } catch (_) {
      return '';
    }
  }

  String get addressShort {
    final addr = tokenAddress ?? '';
    if (addr.length < 12) return addr;
    return '${addr.substring(0, 6)}...${addr.substring(addr.length - 4)}';
  }
}

class ExecutionSummary {
  final double totalBuyUsd;
  final double totalSellUsd;
  final double realizedPnl;
  final double totalGasUsd;
  final int buyCount;
  final int sellCount;
  final int confirmedCount;
  final int failedCount;
  final int totalCount;

  const ExecutionSummary({
    this.totalBuyUsd = 0,
    this.totalSellUsd = 0,
    this.realizedPnl = 0,
    this.totalGasUsd = 0,
    this.buyCount = 0,
    this.sellCount = 0,
    this.confirmedCount = 0,
    this.failedCount = 0,
    this.totalCount = 0,
  });

  factory ExecutionSummary.fromJson(Map<String, dynamic> json) =>
      ExecutionSummary(
        totalBuyUsd: (json['total_buy_usd'] as num?)?.toDouble() ?? 0,
        totalSellUsd: (json['total_sell_usd'] as num?)?.toDouble() ?? 0,
        realizedPnl: (json['realized_pnl'] as num?)?.toDouble() ?? 0,
        totalGasUsd: (json['total_gas_usd'] as num?)?.toDouble() ?? 0,
        buyCount: (json['buy_count'] as num?)?.toInt() ?? 0,
        sellCount: (json['sell_count'] as num?)?.toInt() ?? 0,
        confirmedCount: (json['confirmed_count'] as num?)?.toInt() ?? 0,
        failedCount: (json['failed_count'] as num?)?.toInt() ?? 0,
        totalCount: (json['total_count'] as num?)?.toInt() ?? 0,
      );

  bool get hasTrades => totalCount > 0;
  bool get isProfit => realizedPnl > 0;
}

class ExecutionsResponse {
  final List<AgentExecution> executions;
  final ExecutionSummary summary;

  const ExecutionsResponse({
    required this.executions,
    required this.summary,
  });

  factory ExecutionsResponse.fromJson(Map<String, dynamic> json) =>
      ExecutionsResponse(
        executions: (json['data'] as List<dynamic>? ?? [])
            .map((e) => AgentExecution.fromJson(e as Map<String, dynamic>))
            .toList(),
        summary: ExecutionSummary.fromJson(
            json['summary'] as Map<String, dynamic>? ?? {}),
      );
}
