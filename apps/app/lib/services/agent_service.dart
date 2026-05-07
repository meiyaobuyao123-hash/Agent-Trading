import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/app_config.dart';
import '../models/review.dart';
import '../models/semantic_rule.dart';
import 'auth_service.dart';

/// Agent API 服务 — 对接后端 FastAPI
class AgentService {
  static final AgentService instance = AgentService._();
  AgentService._();

  final _client = http.Client();

  static const _apiBase = AppConfig.backendBaseUrl;
  static const _timeout = Duration(seconds: 90);

  /// R47 P3 — attach Bearer token(否则后端按 dev-user 处理,扣费扣到 dev 账上)
  Map<String, String> get _headers {
    final m = <String, String>{'Content-Type': 'application/json'};
    final token = AuthService.instance.token;
    if (token != null && token.isNotEmpty) {
      m['Authorization'] = 'Bearer $token';
    }
    return m;
  }

  /// 解析后端错误信息
  String _parseError(http.Response resp) {
    try {
      final body = jsonDecode(resp.body) as Map<String, dynamic>;
      return body['detail'] as String? ?? 'Server error (${resp.statusCode})';
    } catch (_) {
      return 'Server error (${resp.statusCode})';
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
      throw AgentException('Network error');
    }
  }

  /// 流式对话（打字机效果）— 返回 `Stream<StreamEvent>`
  /// 每个 event: {"type":"delta","text":"..."} | {"type":"strategy","data":{...}} | {"type":"done"}
  Stream<StreamEvent> chatStream(String message,
      {Map<String, dynamic>? context}) async* {
    try {
      final request = http.Request(
        'POST',
        Uri.parse('$_apiBase/api/agent/chat/stream'),
      );
      request.headers.addAll(_headers);
      request.body = jsonEncode({
        'message': message,
        if (context != null) 'context': context,
      });

      final response = await _client.send(request).timeout(_timeout);

      if (response.statusCode == 401) {
        // R47 P3 — token 过期 → 自动 logout(UI 监听 AuthService → 跳 LoginPage)
        await AuthService.instance.logout();
        yield StreamEvent(type: 'error', text: '登录已过期,请重新登录');
        return;
      }
      if (response.statusCode != 200) {
        yield StreamEvent(type: 'error', text: 'Server error (${response.statusCode})');
        return;
      }

      String buffer = '';
      await for (final chunk in response.stream.transform(utf8.decoder)) {
        buffer += chunk;
        // 按行分割 SSE
        while (buffer.contains('\n')) {
          final idx = buffer.indexOf('\n');
          final line = buffer.substring(0, idx).trim();
          buffer = buffer.substring(idx + 1);

          if (line.startsWith('data: ')) {
            try {
              final data = jsonDecode(line.substring(6)) as Map<String, dynamic>;
              yield StreamEvent.fromJson(data);
            } catch (_) {
              // 忽略 JSON 解析错误
            }
          }
        }
      }
    } catch (e) {
      // 流式失败 → 尝试非流式 fallback
      try {
        final fallback = await chat(message, context: context);
        yield StreamEvent(type: 'delta', text: fallback.message);
        if (fallback.strategy != null) {
          yield StreamEvent(type: 'strategy', strategyData: fallback.strategy);
        }
        yield StreamEvent(type: 'done');
      } catch (e2) {
        yield StreamEvent(type: 'error', text: e2.toString());
      }
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
        throw AgentException('Invalid response format');
      }
      throw AgentException(_parseError(resp));
    } on AgentException {
      rethrow;
    } catch (e) {
      throw AgentException('Network error: $e');
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

  Future<bool> renameStrategy(String id, String newName) async {
    try {
      final resp = await _client
          .put(
            Uri.parse('$_apiBase/api/agent/strategies/$id/rename'),
            headers: _headers,
            body: json.encode({'name': newName}),
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

  // ═══════════════════════════════════════════════════════
  // 模拟盘 + 表现 + 回测 + 模板
  // ═══════════════════════════════════════════════════════

  /// 获取模拟盘交易记录
  Future<List<Map<String, dynamic>>> getPaperTrades(String strategyId) async {
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/agent/paper-trades?strategy_id=$strategyId'),
        headers: _headers,
      ).timeout(_timeout);
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body);
        return (data is List ? data : data['trades'] ?? []).cast<Map<String, dynamic>>();
      }
      return [];
    } catch (_) { return []; }
  }

  /// 获取模拟盘统计
  Future<Map<String, dynamic>> getPaperStats(String strategyId) async {
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/agent/paper-stats/$strategyId'),
        headers: _headers,
      ).timeout(_timeout);
      if (resp.statusCode == 200) return jsonDecode(resp.body) as Map<String, dynamic>;
      return {};
    } catch (_) { return {}; }
  }

  /// [deprecated R37 path] 切换到实盘 — 走 R37 5 项门槛(新策略切不动)
  Future<bool> goLive(String strategyId) async {
    try {
      final resp = await _client.post(
        Uri.parse('$_apiBase/api/agent/strategies/$strategyId/go-live'),
        headers: _headers,
      ).timeout(_timeout);
      return resp.statusCode == 200;
    } catch (_) { return false; }
  }

  /// R42 P0.4 用户主动 promote → live(取代 goLive)
  /// 4 项解锁条件全满足后,bypass R37 5 项硬门槛
  Future<Map<String, dynamic>> promoteToLive(
    String strategyId, {
    required bool hasWallet,
    required bool disclaimerAccepted,
    required bool riskAcknowledged,
    double? maxPositionUsd,
  }) async {
    try {
      final resp = await _client.post(
        Uri.parse('$_apiBase/api/agent/strategies/$strategyId/promote-to-live'),
        headers: _headers,
        body: jsonEncode({
          'has_wallet': hasWallet,
          'disclaimer_accepted': disclaimerAccepted,
          'risk_acknowledged': riskAcknowledged,
          if (maxPositionUsd != null) 'max_position_usd': maxPositionUsd,
        }),
      ).timeout(_timeout);
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
      return {'promoted': false, 'error': 'HTTP ${resp.statusCode}'};
    } catch (e) {
      return {'promoted': false, 'error': e.toString()};
    }
  }

  /// R42 P0.4 一键降回 paper(无条件成功)
  Future<bool> demoteToPaper(String strategyId) async {
    try {
      final resp = await _client.post(
        Uri.parse('$_apiBase/api/agent/strategies/$strategyId/demote-to-paper'),
        headers: _headers,
      ).timeout(_timeout);
      return resp.statusCode == 200;
    } catch (_) { return false; }
  }

  /// R42 P0.5 更新策略风控参数(滑点/止盈止损/MEV/Gas Fee)
  /// 传 null 字段不改;传值就更新
  Future<bool> updateRiskParams(
    String strategyId, {
    double? maxSlippagePct,
    double? stopLossPct,
    double? takeProfitPct,
    double? maxPositionUsd,
    double? trailingStopPct,
    double? priorityFeeSol,
    double? mevBribeSol,
  }) async {
    try {
      final body = <String, dynamic>{};
      if (maxSlippagePct != null) body['max_slippage_pct'] = maxSlippagePct;
      if (stopLossPct != null) body['stop_loss_pct'] = stopLossPct;
      if (takeProfitPct != null) body['take_profit_pct'] = takeProfitPct;
      if (maxPositionUsd != null) body['max_position_usd'] = maxPositionUsd;
      if (trailingStopPct != null) body['trailing_stop_pct'] = trailingStopPct;
      if (priorityFeeSol != null) body['priority_fee_sol'] = priorityFeeSol;
      if (mevBribeSol != null) body['mev_bribe_sol'] = mevBribeSol;
      if (body.isEmpty) return true;
      final resp = await _client.patch(
        Uri.parse('$_apiBase/api/agent/strategies/$strategyId/risk-params'),
        headers: _headers,
        body: jsonEncode(body),
      ).timeout(_timeout);
      return resp.statusCode == 200;
    } catch (_) { return false; }
  }

  /// R42 P1 检查后端 master_key 是否就绪(导入私钥前查一下)
  Future<bool> walletMasterReady() async {
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/wallet/master-status'),
        headers: _headers,
      ).timeout(_timeout);
      if (resp.statusCode == 200) {
        final body = jsonDecode(resp.body) as Map<String, dynamic>;
        return body['ready'] == true;
      }
      return false;
    } catch (_) { return false; }
  }

  /// R42 P1 导入钱包到后端(AES 加密存 DB)
  /// 返:{success, error?, wallet?{id,public_key,chain,...}}
  Future<Map<String, dynamic>> importWalletToBackend({
    required String chain,
    required String publicKey,
    required String privateKey,
    String? label,
    bool setDefault = false,
  }) async {
    try {
      final resp = await _client.post(
        Uri.parse('$_apiBase/api/wallet/import'),
        headers: _headers,
        body: jsonEncode({
          'chain': chain,
          'public_key': publicKey,
          'private_key': privateKey,
          if (label != null) 'label': label,
          'set_default': setDefault,
        }),
      ).timeout(_timeout);
      if (resp.statusCode == 201 || resp.statusCode == 200) {
        return {'success': true, 'wallet': jsonDecode(resp.body)};
      }
      // 解析错误体
      String error = 'HTTP ${resp.statusCode}';
      try {
        final body = jsonDecode(resp.body) as Map<String, dynamic>;
        error = body['detail']?.toString() ?? error;
      } catch (_) {}
      return {'success': false, 'error': error};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  /// R42 P1 列出后端钱包(不含私钥)
  Future<List<Map<String, dynamic>>> listBackendWallets() async {
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/wallet/list'),
        headers: _headers,
      ).timeout(_timeout);
      if (resp.statusCode == 200) {
        return (jsonDecode(resp.body) as List).cast<Map<String, dynamic>>();
      }
      return [];
    } catch (_) { return []; }
  }

  /// R42 P0.4 合并交易记录(paper + live)
  Future<Map<String, dynamic>> getTradesMerged(String strategyId, {int limit = 50}) async {
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/agent/trades-merged/$strategyId?limit=$limit'),
        headers: _headers,
      ).timeout(_timeout);
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
      return {'trades': [], 'paper_count': 0, 'live_count': 0, 'total': 0};
    } catch (_) {
      return {'trades': [], 'paper_count': 0, 'live_count': 0, 'total': 0};
    }
  }

  /// 模拟 vs 实盘对比
  Future<Map<String, dynamic>> getComparison(String strategyId) async {
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/agent/compare/$strategyId'),
        headers: _headers,
      ).timeout(_timeout);
      if (resp.statusCode == 200) return jsonDecode(resp.body) as Map<String, dynamic>;
      return {};
    } catch (_) { return {}; }
  }

  /// 获取策略模板列表
  Future<List<Map<String, dynamic>>> getTemplates() async {
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/agent/templates'),
        headers: _headers,
      ).timeout(_timeout);
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body);
        return (data is List ? data : data['templates'] ?? []).cast<Map<String, dynamic>>();
      }
      return [];
    } catch (_) { return []; }
  }

  /// 从模板创建策略
  Future<AgentStrategy?> createFromTemplate(String templateId, {Map<String, dynamic>? overrides}) async {
    try {
      final resp = await _client.post(
        Uri.parse('$_apiBase/api/agent/templates/$templateId/create'),
        headers: _headers,
        body: jsonEncode(overrides ?? {}),
      ).timeout(_timeout);
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final s = data['strategy'] as Map<String, dynamic>?;
        if (s != null) return AgentStrategy.fromJson(s);
      }
      return null;
    } catch (_) { return null; }
  }

  /// 获取 Agent 表现分析
  Future<Map<String, dynamic>> getPerformance() async {
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/agent/performance'),
        headers: _headers,
      ).timeout(_timeout);
      if (resp.statusCode == 200) return jsonDecode(resp.body) as Map<String, dynamic>;
      return {};
    } catch (_) { return {}; }
  }

  /// 获取 Agent 记忆数据
  Future<Map<String, dynamic>> getMemory() async {
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/agent/memory'),
        headers: _headers,
      ).timeout(_timeout);
      if (resp.statusCode == 200) return jsonDecode(resp.body) as Map<String, dynamic>;
      return {};
    } catch (_) { return {}; }
  }

  /// 获取 Regime 状态
  Future<Map<String, dynamic>> getRegime() async {
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/agent/regime'),
        headers: _headers,
      ).timeout(_timeout);
      if (resp.statusCode == 200) return jsonDecode(resp.body) as Map<String, dynamic>;
      return {};
    } catch (_) { return {}; }
  }

  /// 回测策略
  Future<Map<String, dynamic>> backtest(String strategyId, {int days = 7}) async {
    try {
      final resp = await _client.post(
        Uri.parse('$_apiBase/api/agent/backtest'),
        headers: _headers,
        body: jsonEncode({
          'message': strategyId,
          'context': {'strategy_id': strategyId, 'days': days},
        }),
      ).timeout(const Duration(seconds: 120));
      if (resp.statusCode == 200) return jsonDecode(resp.body) as Map<String, dynamic>;
      return {};
    } catch (_) { return {}; }
  }

  // ═══════════════════════════════════════════════════════════════
  // W3 D3 — Thesis(S08 thesis-writer)
  // 引用 docs/agent-pm/05-tool-catalog.md S08
  // 引用 services/pump-scanner/api/routes_thesis.py(MOCK_MODE 返 fixture)
  // ═══════════════════════════════════════════════════════════════

  /// 触发新 thesis 生成
  ///
  /// [chain] solana / eth / bsc / base
  /// [address] 代币合约地址
  /// [level] 'auto' / 'L1' / 'L2' / 'L3'(默认 auto 由后端决定)
  /// 后端 MOCK_MODE=true 时返 fixture(W7-W12 实施真实 thesis_loop)
  Future<Map<String, dynamic>?> requestThesis({
    required String chain,
    required String address,
    String level = 'auto',
  }) async {
    try {
      final resp = await _client.post(
        Uri.parse('$_apiBase/api/thesis'),
        headers: _headers,
        body: jsonEncode({
          'chain': chain,
          'address': address,
          'level': level,
        }),
      ).timeout(const Duration(seconds: 30));
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
      return null;
    } catch (_) {
      return null;
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // W3 D4 — HITL 待审批队列
  // 引用 services/pump-scanner/api/routes_agent.py W3 D4
  // 引用 docs/agent-pm/05-tool-catalog.md T09 create_approval_request
  // ═══════════════════════════════════════════════════════════════

  /// 列出 HITL 待审批队列
  Future<List<Map<String, dynamic>>> getPendingApprovals({
    String status = 'pending',
    int limit = 20,
  }) async {
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/agent/pending-approvals?status=$status&limit=$limit'),
        headers: _headers,
      ).timeout(const Duration(seconds: 15));
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        return (data['approvals'] as List? ?? const [])
            .cast<Map<String, dynamic>>();
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  /// 批准 HITL(传签名)
  /// 返回 {ok, status, tx_hash?} 或 null(失败)
  Future<Map<String, dynamic>?> approvePendingApproval(
    String approvalId, {
    required String signature,
    String? note,
  }) async {
    try {
      final resp = await _client.post(
        Uri.parse('$_apiBase/api/agent/pending-approvals/$approvalId/approve'),
        headers: _headers,
        body: jsonEncode({
          'signature': signature,
          if (note != null) 'note': note,
        }),
      ).timeout(const Duration(seconds: 30));
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
      return null;
    } catch (_) {
      return null;
    }
  }

  /// 拒绝 HITL(可选 note)
  Future<bool> rejectPendingApproval(
    String approvalId, {
    String? note,
  }) async {
    try {
      final resp = await _client.post(
        Uri.parse('$_apiBase/api/agent/pending-approvals/$approvalId/reject'),
        headers: _headers,
        body: jsonEncode({
          if (note != null) 'note': note,
        }),
      ).timeout(const Duration(seconds: 15));
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ═══════════════════════════════════════════════════════
  // 复盘 / 规则 / 记忆 (S07 review-engine + Memory)
  // 后端尚未实施 → 返回 mock 数据,Flutter UI 可联调
  // ═══════════════════════════════════════════════════════

  /// 获取复盘报告(daily/weekly/monthly)。后端 endpoint 暂未实施,返 mock。
  Future<Review?> getReview(String period, {DateTime? date}) async {
    final d = date ?? DateTime.now();
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/agent/reviews?period=$period'
            '&date=${d.toIso8601String().substring(0, 10)}'),
        headers: _headers,
      ).timeout(const Duration(seconds: 15));
      if (resp.statusCode == 200) {
        return Review.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
      }
    } catch (_) {/* fallthrough to mock */}
    return _mockReview(period, d);
  }

  Review _mockReview(String period, DateTime d) {
    final from = period == 'daily'
        ? d.subtract(const Duration(days: 1))
        : period == 'weekly'
            ? d.subtract(const Duration(days: 7))
            : d.subtract(const Duration(days: 30));
    return Review(
      reviewId: 'mock-${period}-${d.millisecondsSinceEpoch}',
      period: period,
      periodFrom: from,
      periodTo: d,
      summary: ReviewSummary(
        headline: period == 'daily'
            ? '今日 4 笔 — 胜率 75%,EV +2.1%'
            : period == 'weekly'
                ? '本周 18 笔 — 胜率 61%,EV +1.4%,夏普 1.8'
                : '本月 64 笔 — 胜率 58%,EV +1.1%,最大回撤 -6.2%',
        body: period == 'daily'
            ? '上午 SOL TRENDING_UP,聪明钱跟单 3 笔全胜;下午 EVM regime 转 RANGING,1 笔小亏出场。整体执行符合策略框架。'
            : '本期 RANGING 与 TRENDING_UP 各占一半。聪明钱跟单策略胜率明显高于规则触发,建议在 RANGING 期间收紧 BC 进场阈值至 8%。',
      ),
      insights: [
        const Insight(
          type: 'win_pattern',
          text: '聪明钱 elite ≥ 75 + 流动性 > \$50K + Regime ∈ {TRENDING_UP, BREAKOUT} 时,胜率 78% (n=14)',
          evidenceTradeIds: ['t-2031', 't-2034', 't-2038'],
          llmJudgeScore: 0.82,
        ),
        const Insight(
          type: 'loss_pattern',
          text: 'BC < 5% + 持有时长 > 4h 全部亏损 (n=5),建议加 4h 强制平仓',
          evidenceTradeIds: ['t-1998', 't-2001', 't-2007'],
          llmJudgeScore: 0.71,
        ),
        const Insight(
          type: 'risk_warning',
          text: 'CRISIS 期间 1 笔仍触发(HR16 已修),整体风险暴露在阈值内',
          evidenceTradeIds: ['t-2042'],
          llmJudgeScore: 0.65,
        ),
      ],
      ruleProposals: [
        const RuleProposal(
          proposalId: 'rp-001',
          humanReadable: 'RANGING regime 期间,BC 进场阈值从 5% 收紧到 8%',
          formalCondition: {
            'when': {'regime': 'RANGING', 'bc_pct': {'<': 8}},
            'then': {'block_entry': true},
          },
          sampleSize: 22,
          winRateDiff: 12.4,
          wilsonCiLower: 0.58,
          activeRegimes: ['RANGING'],
          reflectionId: 'refl-2026-04-29',
        ),
        const RuleProposal(
          proposalId: 'rp-002',
          humanReadable: 'BC < 5% 且持仓 > 4h 强制平仓',
          formalCondition: {
            'when': {'bc_pct': {'<': 5}, 'hold_hours': {'>': 4}},
            'then': {'force_close': true},
          },
          sampleSize: 14,
          winRateDiff: 8.7,
          wilsonCiLower: 0.51,
          activeRegimes: ['RANGING', 'HIGH_VOLATILITY'],
          reflectionId: 'refl-2026-04-30',
        ),
      ],
      metrics: ReviewMetrics(
        tradeCount: period == 'daily' ? 4 : (period == 'weekly' ? 18 : 64),
        winRate: 0.61,
        evPct: 1.4,
        sharpe: 1.8,
        maxDrawdownPct: -6.2,
        profitFactor: 1.92,
        klyFraction: 0.18,
      ),
      coldStartState: 'normal',
    );
  }

  /// 列出 Semantic Memory 规则。后端 endpoint 暂未实施,返 mock。
  Future<List<SemanticRule>> listSemanticRules() async {
    try {
      final resp = await _client.get(
        Uri.parse('$_apiBase/api/agent/memory/rules'),
        headers: _headers,
      ).timeout(const Duration(seconds: 15));
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        return (data['rules'] as List? ?? const [])
            .map((x) => SemanticRule.fromJson(x as Map<String, dynamic>))
            .toList();
      }
    } catch (_) {/* fallthrough to mock */}
    return _mockSemanticRules();
  }

  List<SemanticRule> _mockSemanticRules() {
    final now = DateTime.now();
    return [
      SemanticRule(
        ruleId: 'sm-001',
        humanReadable: '聪明钱 elite ≥ 75 + 流动性 > \$50K → 仓位上调 20%',
        formalCondition: const {
          'when': {'smart_score': {'>=': 75}, 'liquidity_usd': {'>': 50000}},
          'then': {'position_size_multiplier': 1.2},
        },
        activeRegimes: const ['TRENDING_UP', 'BREAKOUT'],
        evidence: const RuleEvidence(
          sampleSize: 28,
          winRateDiff: 14.2,
          tTestP: 0.03,
          wilsonCiLower: 0.62,
          regimesObserved: ['TRENDING_UP', 'BREAKOUT'],
        ),
        status: RuleStatus.active,
        matchCount: 47,
        proposeCount: 1,
        createdAt: now.subtract(const Duration(days: 21)),
        updatedAt: now.subtract(const Duration(days: 2)),
      ),
      SemanticRule(
        ruleId: 'sm-002',
        humanReadable: 'CRISIS regime → 全局禁止开新仓',
        formalCondition: const {
          'when': {'regime': 'CRISIS'},
          'then': {'block_entry': true},
        },
        activeRegimes: const ['CRISIS'],
        evidence: const RuleEvidence(
          sampleSize: 8,
          winRateDiff: -22.0,
          regimesObserved: ['CRISIS'],
        ),
        status: RuleStatus.active,
        matchCount: 3,
        proposeCount: 0,
        createdAt: now.subtract(const Duration(days: 32)),
        updatedAt: now.subtract(const Duration(days: 5)),
      ),
      SemanticRule(
        ruleId: 'sm-003',
        humanReadable: 'RANGING regime → BC 进场阈值收紧到 8% (Shadow)',
        formalCondition: const {
          'when': {'regime': 'RANGING', 'bc_pct': {'<': 8}},
          'then': {'block_entry': true},
        },
        activeRegimes: const ['RANGING'],
        evidence: const RuleEvidence(
          sampleSize: 22,
          winRateDiff: 12.4,
          wilsonCiLower: 0.58,
          regimesObserved: ['RANGING'],
        ),
        status: RuleStatus.shadow,
        shadowModeUntil: now.add(const Duration(days: 9)),
        matchCount: 2,
        proposeCount: 1,
        createdAt: now.subtract(const Duration(days: 5)),
        updatedAt: now.subtract(const Duration(hours: 3)),
      ),
      SemanticRule(
        ruleId: 'sm-004',
        humanReadable: 'KOL Tier-1 sentiment > 0.7 → 加权进场分 +5',
        formalCondition: const {
          'when': {'kol_tier': 1, 'sentiment': {'>': 0.7}},
          'then': {'score_bonus': 5},
        },
        activeRegimes: const ['TRENDING_UP'],
        evidence: const RuleEvidence(
          sampleSize: 12,
          winRateDiff: 6.0,
          regimesObserved: ['TRENDING_UP'],
        ),
        status: RuleStatus.dormant,
        dormantSince: now.subtract(const Duration(days: 31)),
        matchCount: 0,
        proposeCount: 0,
        createdAt: now.subtract(const Duration(days: 80)),
        updatedAt: now.subtract(const Duration(days: 31)),
      ),
    ];
  }

  /// 启用/禁用规则
  Future<bool> updateRule(String ruleId, {required bool enabled}) async {
    try {
      final resp = await _client.patch(
        Uri.parse('$_apiBase/api/agent/memory/rules/$ruleId'),
        headers: _headers,
        body: jsonEncode({'status': enabled ? 'active' : 'disabled'}),
      ).timeout(const Duration(seconds: 15));
      return resp.statusCode == 200;
    } catch (_) {
      return true; // mock 返成功
    }
  }

  /// 删除规则
  Future<bool> deleteRule(String ruleId) async {
    try {
      final resp = await _client.delete(
        Uri.parse('$_apiBase/api/agent/memory/rules/$ruleId'),
        headers: _headers,
      ).timeout(const Duration(seconds: 15));
      return resp.statusCode == 200;
    } catch (_) {
      return true; // mock 返成功
    }
  }

  /// 采纳规则提议(T11 approve_rule)
  Future<bool> approveRuleProposal(String proposalId) async {
    try {
      final resp = await _client.post(
        Uri.parse('$_apiBase/api/agent/memory/rule-proposals/$proposalId/approve'),
        headers: _headers,
      ).timeout(const Duration(seconds: 15));
      return resp.statusCode == 200;
    } catch (_) {
      return true; // mock 返成功
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
        name: json['name'] as String? ?? 'Unnamed',
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

  String get statusLabel => status;

  String get timeAgo {
    if (createdAt.isEmpty) return '';
    try {
      final dt = DateTime.parse(createdAt);
      final diff = DateTime.now().toUtc().difference(dt);
      if (diff.inMinutes < 1) return 'now';
      if (diff.inMinutes < 60) return '${diff.inMinutes}m';
      if (diff.inHours < 24) return '${diff.inHours}h';
      return '${diff.inDays}d';
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

/// 流式事件模型
class StreamEvent {
  final String type; // start, delta, strategy, done, error
  final String? text;
  final Map<String, dynamic>? strategyData;

  const StreamEvent({required this.type, this.text, this.strategyData});

  factory StreamEvent.fromJson(Map<String, dynamic> json) => StreamEvent(
        type: json['type'] as String? ?? 'unknown',
        text: json['text'] as String?,
        strategyData: json['data'] as Map<String, dynamic>?,
      );

  bool get isDelta => type == 'delta';
  bool get isDone => type == 'done';
  bool get isError => type == 'error';
  bool get isStrategy => type == 'strategy';
}
