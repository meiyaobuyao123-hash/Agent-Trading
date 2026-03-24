import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../l10n/app_localizations.dart';
import '../../theme/app_colors.dart';
import '../../services/agent_service.dart';
import '../../services/wallet_service.dart';
import '../../widgets/strategy_detail_sheet.dart';
import 'strategy_detail_page.dart';
import 'ai_insights_tab.dart';

/// Agent 策略中心 — 对话 + 策略管理 + AI 洞察
class AgentScreen extends StatefulWidget {
  const AgentScreen({super.key});

  @override
  State<AgentScreen> createState() => _AgentScreenState();
}

class _AgentScreenState extends State<AgentScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tab;

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 3, vsync: this);
    // 首次进入 Agent 页面时弹出合规声明
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _checkAgentDisclaimer();
    });
  }

  /// 检查是否首次使用 Agent，首次使用弹出合规声明
  Future<void> _checkAgentDisclaimer() async {
    final prefs = await SharedPreferences.getInstance();
    final shown = prefs.getBool('agent_disclaimer_shown') ?? false;
    if (!shown && mounted) {
      await _showAgentDisclaimerDialog();
      // 无论用户是否真正阅读，点击后即标记（按钮只有一个，必须点击才能关闭）
      await prefs.setBool('agent_disclaimer_shown', true);
    }
  }

  /// Agent 合规声明弹窗 — 只有一个"我已阅读并同意"按钮，必须点击才能继续
  Future<void> _showAgentDisclaimerDialog() async {
    if (!mounted) return;
    final c = context.colors;
    await showDialog<void>(
      context: context,
      barrierDismissible: false, // 强制点击按钮，不允许点击外部关闭
      builder: (ctx) => AlertDialog(
        backgroundColor: c.bgSecondary,
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Icon(Icons.info_outline_rounded, color: c.primary, size: 22),
            const SizedBox(width: 8),
            Text(
              S.of(ctx).usageNotice,
              style: TextStyle(
                color: c.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 主说明
            Text(
              S.of(ctx).agentDisclaimer1,
              style: TextStyle(
                color: c.textPrimary,
                fontSize: 14,
                fontWeight: FontWeight.w600,
                height: 1.5,
              ),
            ),
            const SizedBox(height: 12),
            // 条目列表
            _agentDisclaimerItem(c, S.of(ctx).riskSelfBorne),
            _agentDisclaimerItem(c, S.of(ctx).noPlatformLicense),
            _agentDisclaimerItem(
                c, S.of(ctx).autoTradeRisk,
                isWarning: true),
            _agentDisclaimerItem(
                c, S.of(ctx).platformNotResponsible,
                isWarning: true),
          ],
        ),
        actions: [
          // 只有一个按钮，必须点击才能关闭
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(),
            style: FilledButton.styleFrom(
              backgroundColor: c.primary,
              minimumSize: const Size(double.infinity, 44),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
            child: Text(
              S.of(ctx).iReadAndAgree,
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            ),
          ),
        ],
        actionsAlignment: MainAxisAlignment.center,
        actionsPadding:
            const EdgeInsets.fromLTRB(16, 0, 16, 16),
      ),
    );
  }

  @override
  void dispose() {
    _tab.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: NestedScrollView(
        headerSliverBuilder: (_, __) => [
          SliverAppBar(
            pinned: true,
            backgroundColor: c.bg,
            title: Text(
              S.of(context).agentStrategy,
              style: TextStyle(
                color: c.textPrimary,
                fontSize: 20,
                fontWeight: FontWeight.w600,
                letterSpacing: -0.3,
              ),
            ),
            bottom: TabBar(
              controller: _tab,
              indicatorColor: c.primary,
              indicatorWeight: 2,
              labelColor: c.primary,
              unselectedLabelColor: c.textTertiary,
              labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
              tabs: [
                Tab(text: S.of(context).chatTab),
                Tab(text: S.of(context).myStrategyTab),
                const Tab(text: 'AI 洞察'),
              ],
            ),
          ),
        ],
        body: TabBarView(
          controller: _tab,
          children: const [
            _ChatTab(),
            _MyStrategiesTab(),
            const AiInsightsTab(),
          ],
        ),
      ),
    );
  }
}

// ── Agent 合规声明弹窗辅助函数 ──────────────────────────────

/// Agent 合规声明条目 Widget
Widget _agentDisclaimerItem(AppColorScheme c, String text,
    {bool isWarning = false}) {
  return Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          isWarning ? Icons.warning_amber_rounded : Icons.circle,
          color: isWarning ? c.warning : c.textTertiary,
          size: isWarning ? 16 : 6,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            text,
            style: TextStyle(
              color: c.textSecondary,
              fontSize: 13,
              height: 1.4,
            ),
          ),
        ),
      ],
    ),
  );
}

// ══════════════════════════════════════════════════════
// Tab 1: 策略对话（AI 对话窗口）
// ══════════════════════════════════════════════════════

class _ChatTab extends StatefulWidget {
  const _ChatTab();

  @override
  State<_ChatTab> createState() => _ChatTabState();
}

class _ChatTabState extends State<_ChatTab>
    with AutomaticKeepAliveClientMixin {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final _messages = <_ChatMessage>[];
  bool _sending = false;

  /// 流式消息专用 — 避免 setState 全局 rebuild 导致闪烁
  final ValueNotifier<String> _streamText = ValueNotifier('');
  bool _isStreamingActive = false;

  /// 待确认的策略规范
  Map<String, dynamic>? _pendingStrategy;
  String? _pendingPrompt;
  String? _strategyError;

  @override
  bool get wantKeepAlive => true;

  bool _introAdded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_introAdded) {
      _introAdded = true;
      _messages.add(_ChatMessage(
        isUser: false,
        text: S.of(context).agentIntro,
      ));
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    _streamText.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _sending) return;

    // 1. 添加用户消息 + 开启流式状态
    setState(() {
      _messages.add(_ChatMessage(isUser: true, text: text));
      _sending = true;
      _isStreamingActive = true;
      _streamText.value = '';
    });
    _controller.clear();
    _scrollToBottom();

    Map<String, dynamic>? strategyData;

    try {
      await for (final event in AgentService.instance.chatStream(text)) {
        if (!mounted) return;

        if (event.isDelta && event.text != null) {
          // 只更新 ValueNotifier，不触发 setState → 零闪烁
          _streamText.value += event.text!;
          _scrollToBottom();
        } else if (event.isStrategy && event.strategyData != null) {
          strategyData = event.strategyData;
        } else if (event.isDone) {
          break;
        } else if (event.isError) {
          _streamText.value += event.text ?? 'Unknown error';
          break;
        }
      }
    } catch (e) {
      if (_streamText.value.isEmpty) {
        _streamText.value = 'Network error';
      }
    }

    if (!mounted) return;

    // 2. 流式结束 → 固化为普通消息
    final finalText = _streamText.value;
    setState(() {
      _isStreamingActive = false;
      _messages.add(_ChatMessage(isUser: false, text: finalText));
      if (strategyData != null) {
        _pendingStrategy = strategyData;
        _pendingPrompt = text;
        _strategyError = null;
      }
      _sending = false;
    });
    if (mounted) _scrollToBottom();
  }

  /// 确认创建策略 — 由 ConfirmCard 调用，返回 true 表示成功
  Future<bool> _confirmStrategy(Map<String, dynamic> extraParams) async {
    if (_pendingStrategy == null) return false;

    // 合并交易参数到策略 risk_params
    final spec = Map<String, dynamic>.from(_pendingStrategy!);
    if (extraParams.isNotEmpty) {
      spec['risk_params'] = {
        ...?(spec['risk_params'] as Map<String, dynamic>?),
        ...extraParams,
      };
    }

    try {
      final result = await AgentService.instance.createStrategy(
        spec,
        sourcePrompt: _pendingPrompt,
      );
      if (!mounted) return false;
      setState(() {
        _messages.add(_ChatMessage(
          isUser: false,
          text: S.of(context).strategyCreated(result.name),
        ));
        _pendingStrategy = null;
        _pendingPrompt = null;
        _strategyError = null;
      });
      _scrollToBottom();
      return true;
    } on AgentException catch (e) {
      if (!mounted) return false;
      setState(() => _strategyError = e.message);
      return false;
    }
  }

  void _cancelStrategy() {
    setState(() {
      _pendingStrategy = null;
      _pendingPrompt = null;
      _strategyError = null;
      _messages.add(_ChatMessage(
        isUser: false,
        text: S.of(context).cancelled,
      ));
    });
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    super.build(context); // AutomaticKeepAliveClientMixin 要求
    return Column(
      children: [
        Expanded(
          child: ListView.builder(
            controller: _scrollController,
            padding: const EdgeInsets.all(16),
            itemCount: _messages.length +
                (_isStreamingActive ? 1 : 0) +
                (_pendingStrategy != null ? 1 : 0),
            itemBuilder: (ctx, i) {
              if (i < _messages.length) {
                final msg = _messages[i];
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: msg.isUser
                      ? _UserBubble(text: msg.text)
                      : _AiBubble(text: msg.text),
                );
              }
              // 流式消息（用 ValueListenableBuilder 避免闪烁）
              if (_isStreamingActive && i == _messages.length) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: ValueListenableBuilder<String>(
                    valueListenable: _streamText,
                    builder: (ctx, text, _) => _AiBubble(
                      text: text,
                      isStreaming: true,
                    ),
                  ),
                );
              }
              if (_pendingStrategy != null) {
                return _ConfirmCard(
                  strategy: _pendingStrategy!,
                  error: _strategyError,
                  onConfirm: _confirmStrategy,
                  onCancel: _cancelStrategy,
                );
              }
              return const SizedBox.shrink();
            },
          ),
        ),
        _ChatInput(
          controller: _controller,
          enabled: !_sending,
          onSend: _send,
        ),
      ],
    );
  }
}

class _ChatMessage {
  final bool isUser;
  final String text;
  final bool isStreaming;
  const _ChatMessage({required this.isUser, required this.text, this.isStreaming = false});
}

class _AiBubble extends StatelessWidget {
  final String text;
  final bool isStreaming;
  const _AiBubble({required this.text, this.isStreaming = false});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: c.primaryLight,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(Icons.smart_toy_rounded,
              color: c.primary, size: 20),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: c.cardGlass,
              borderRadius: const BorderRadius.only(
                topRight: Radius.circular(16),
                bottomLeft: Radius.circular(16),
                bottomRight: Radius.circular(16),
              ),
              border: Border.all(color: c.glassBorder, width: 0.5),
            ),
            child: RichText(
              text: TextSpan(
                style: TextStyle(
                  color: c.textPrimary,
                  fontSize: 14,
                  height: 1.6,
                ),
                children: [
                  TextSpan(text: text),
                  if (isStreaming)
                    WidgetSpan(
                      child: _BlinkingCursor(color: c.primary),
                    ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _BlinkingCursor extends StatefulWidget {
  final Color color;
  const _BlinkingCursor({required this.color});

  @override
  State<_BlinkingCursor> createState() => _BlinkingCursorState();
}

class _BlinkingCursorState extends State<_BlinkingCursor>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _ctrl,
      child: Container(
        width: 2,
        height: 16,
        margin: const EdgeInsets.only(left: 1),
        color: widget.color,
      ),
    );
  }
}

class _UserBubble extends StatelessWidget {
  final String text;
  const _UserBubble({required this.text});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        const SizedBox(width: 48),
        Flexible(
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              gradient: c.primaryGradient,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(16),
                bottomLeft: Radius.circular(16),
                bottomRight: Radius.circular(16),
              ),
            ),
            child: Text(
              text,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 14,
                height: 1.5,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _TypingIndicator extends StatelessWidget {
  const _TypingIndicator();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: c.primaryLight,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(Icons.smart_toy_rounded,
                color: c.primary, size: 20),
          ),
          const SizedBox(width: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              color: c.cardGlass,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: c.glassBorder, width: 0.5),
            ),
            child: SizedBox(
              width: 36,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: List.generate(3, (i) => _PulseDot(
                  delay: Duration(milliseconds: i * 200),
                  color: c.textTertiary,
                )),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PulseDot extends StatefulWidget {
  final Duration delay;
  final Color color;
  const _PulseDot({required this.delay, required this.color});

  @override
  State<_PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<_PulseDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    );
    Future.delayed(widget.delay, () {
      if (mounted) _ctrl.repeat(reverse: true);
    });
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) => Opacity(
        opacity: 0.3 + 0.7 * _ctrl.value,
        child: Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(
            color: widget.color,
            shape: BoxShape.circle,
          ),
        ),
      ),
    );
  }
}

/// 策略确认卡片 — 含钱包选择 + 止盈止损 + 交易参数
///
/// UX 设计：
/// 1. 点击「创建策略」→ 按钮显示 loading → 调用 API
/// 2. 成功 → 卡片消失 → 成功消息出现在聊天中
/// 3. 失败 → 卡片保留，显示错误，按钮恢复可点击
/// 4. 点击「取消」→ 卡片立刻消失 → 取消消息
class _ConfirmCard extends StatefulWidget {
  final Map<String, dynamic> strategy;
  final String? error;
  final Future<bool> Function(Map<String, dynamic> params) onConfirm;
  final VoidCallback onCancel;
  const _ConfirmCard({
    required this.strategy,
    this.error,
    required this.onConfirm,
    required this.onCancel,
  });

  @override
  State<_ConfirmCard> createState() => _ConfirmCardState();
}

class _ConfirmCardState extends State<_ConfirmCard> {
  String? _selectedWalletId;
  bool _loading = false;
  bool _showAdvanced = false;

  // 交易参数
  double _slippage = 1.0;
  double _stopLoss = 30.0;
  double _takeProfit = 100.0;
  double _priorityFee = 0.0005;
  double _mevBribe = 0.0;

  @override
  void initState() {
    super.initState();
    final wallets = WalletService.instance.wallets;
    if (wallets.isNotEmpty) {
      _selectedWalletId = WalletService.instance.defaultWalletId ?? wallets.first.id;
    }
    // 从策略的 risk_params 初始化默认值
    final rp = widget.strategy['risk_params'] as Map<String, dynamic>?;
    if (rp != null) {
      _stopLoss = ((rp['stop_loss_pct'] as num?) ?? 0.30) * 100;
      _takeProfit = ((rp['take_profit_pct'] as num?) ?? 1.0) * 100;
      _slippage = (rp['max_slippage_pct'] as num?)?.toDouble() ?? 1.0;
      _priorityFee = (rp['priority_fee_sol'] as num?)?.toDouble() ?? 0.0005;
      _mevBribe = (rp['mev_bribe_sol'] as num?)?.toDouble() ?? 0.0;
    }
  }

  Future<void> _handleConfirm() async {
    // 点击"创建策略"前先弹出风险二次确认弹窗
    final confirmed = await _showStrategyRiskDialog(context);
    if (confirmed != true) return; // 用户点击"取消"，不继续

    setState(() => _loading = true);
    final params = <String, dynamic>{
      'stop_loss_pct': _stopLoss / 100,
      'take_profit_pct': _takeProfit / 100,
      'max_slippage_pct': _slippage,
      'priority_fee_sol': _priorityFee,
      'mev_bribe_sol': _mevBribe,
      'trailing_stop': true,
      if (_selectedWalletId != null) 'wallet_id': _selectedWalletId,
    };
    final success = await widget.onConfirm(params);
    if (mounted && !success) {
      setState(() => _loading = false);
    }
  }

  /// 启用策略前的风险二次确认弹窗 — 返回 true 表示用户点击"确认启用"
  Future<bool?> _showStrategyRiskDialog(BuildContext context) {
    final c = context.colors;
    final name = widget.strategy['name'] as String? ?? S.of(context).unnamedStrategy;
    return showDialog<bool>(
      context: context,
      barrierDismissible: true,
      builder: (ctx) => AlertDialog(
        backgroundColor: c.bgSecondary,
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Icon(Icons.play_circle_outline_rounded,
                color: c.primary, size: 22),
            const SizedBox(width: 8),
            Text(
              S.of(ctx).confirmEnableStrategy,
              style: TextStyle(
                color: c.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 策略名称提示
            Container(
              padding: const EdgeInsets.symmetric(
                  horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: c.primaryLight,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '\u300C$name\u300D',
                style: TextStyle(
                  color: c.primary,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(height: 12),
            // 说明文字
            Text(
              S.of(ctx).aboutToEnable,
              style: TextStyle(
                color: c.textPrimary,
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 10),
            // 风险条目
            _riskItem(c, S.of(ctx).paramSetByYou),
            _riskItem(c, S.of(ctx).understandRisk, isWarning: true),
            _riskItem(c, S.of(ctx).platformExecuteOnly,
                isWarning: true),
          ],
        ),
        actions: [
          // 取消
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(
              S.of(ctx).cancel,
              style: TextStyle(color: c.textTertiary),
            ),
          ),
          // 确认启用
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: FilledButton.styleFrom(
              backgroundColor: c.primary,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
            child: Text(S.of(ctx).confirmEnable),
          ),
        ],
      ),
    );
  }

  /// 风险确认弹窗条目 Widget
  Widget _riskItem(AppColorScheme c, String text,
      {bool isWarning = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            isWarning
                ? Icons.warning_amber_rounded
                : Icons.check_circle_outline,
            color: isWarning ? c.warning : c.success,
            size: 16,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                color: c.textSecondary,
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final name = widget.strategy['name'] as String? ?? S.of(context).unnamedStrategy;
    final desc = widget.strategy['description'] as String? ?? '';
    final cooldown = widget.strategy['cooldown_minutes'] as int? ?? 30;
    final wallets = WalletService.instance.wallets;
    final hasTradeAction = _hasTradeAction();

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: c.primaryLight,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: c.primary.withValues(alpha: 0.3), width: 1),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── 策略名称 ──
            Row(
              children: [
                Icon(Icons.auto_graph_rounded, color: c.primary, size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(name,
                      style: TextStyle(
                        color: c.textPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      )),
                ),
              ],
            ),
            if (desc.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(desc,
                  style: TextStyle(
                    color: c.textSecondary, fontSize: 13, height: 1.4,
                  )),
            ],
            const SizedBox(height: 4),
            Text(S.of(context).cooldownTime(cooldown),
                style: TextStyle(color: c.textTertiary, fontSize: 12)),

            // ── 止盈止损摘要（交易策略时显示） ──
            if (hasTradeAction) ...[
              const SizedBox(height: 12),
              _paramRow(c, S.of(context).stopLoss, '${_stopLoss.toStringAsFixed(0)}%',
                  Icons.trending_down, c.danger),
              const SizedBox(height: 6),
              _paramRow(c, S.of(context).takeProfit, '${_takeProfit.toStringAsFixed(0)}%',
                  Icons.trending_up, c.success),
              const SizedBox(height: 6),
              _paramRow(c, S.of(context).slippageLabel, '${_slippage.toStringAsFixed(1)}%',
                  Icons.swap_horiz, c.warning),
            ],

            // ── 高级参数折叠区 ──
            if (hasTradeAction) ...[
              const SizedBox(height: 8),
              GestureDetector(
                onTap: () => setState(() => _showAdvanced = !_showAdvanced),
                child: Row(
                  children: [
                    Icon(
                      _showAdvanced ? Icons.expand_less : Icons.expand_more,
                      color: c.textTertiary, size: 18,
                    ),
                    const SizedBox(width: 4),
                    Text(S.of(context).advancedTradeSettings,
                        style: TextStyle(color: c.textTertiary, fontSize: 12)),
                  ],
                ),
              ),
              if (_showAdvanced) ...[
                const SizedBox(height: 8),
                _slider(c, S.of(context).stopLoss, _stopLoss, 5, 50,
                    (v) => setState(() => _stopLoss = v), '%'),
                _slider(c, S.of(context).takeProfit, _takeProfit, 10, 1000,
                    (v) => setState(() => _takeProfit = v), '%'),
                _slider(c, S.of(context).slippageLabel, _slippage, 0.1, 100,
                    (v) => setState(() => _slippage = v), '%'),
                _slider(c, S.of(context).priorityFee, _priorityFee, 0.0001, 0.01,
                    (v) => setState(() => _priorityFee = v), ' SOL'),
                _slider(c, 'MEV', _mevBribe, 0, 0.01,
                    (v) => setState(() => _mevBribe = v), ' SOL'),
              ],
            ],

            // ── 钱包选择 ──
            if (wallets.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(S.of(context).tradingWallet, style: TextStyle(
                color: c.textSecondary, fontSize: 12, fontWeight: FontWeight.w600,
              )),
              const SizedBox(height: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: c.surfaceAlt,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: c.border, width: 0.5),
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<String>(
                    value: _selectedWalletId,
                    isExpanded: true,
                    dropdownColor: c.surface,
                    style: TextStyle(color: c.textPrimary, fontSize: 13),
                    icon: Icon(Icons.keyboard_arrow_down, color: c.textTertiary, size: 20),
                    items: wallets.map((w) => DropdownMenuItem(
                      value: w.id,
                      child: Row(
                        children: [
                          Icon(Icons.account_balance_wallet_outlined,
                              size: 14, color: c.primary),
                          const SizedBox(width: 8),
                          Text(w.name, style: TextStyle(color: c.textPrimary, fontSize: 13)),
                          const SizedBox(width: 6),
                          Text(
                            '${w.address.substring(0, 6)}...${w.address.substring(w.address.length - 4)}',
                            style: TextStyle(color: c.textTertiary, fontSize: 11),
                          ),
                        ],
                      ),
                    )).toList(),
                    onChanged: _loading ? null : (v) => setState(() => _selectedWalletId = v),
                  ),
                ),
              ),
            ] else ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: c.warningLight,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.warning_amber_rounded, color: c.warning, size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        S.of(context).notImported,
                        style: TextStyle(color: c.warning, fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ],

            // ── 错误提示 ──
            if (widget.error != null) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: c.dangerLight,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.error_outline, color: c.danger, size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(widget.error!,
                          style: TextStyle(color: c.danger, fontSize: 12)),
                    ),
                  ],
                ),
              ),
            ],

            // ── 操作按钮 ──
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _loading ? null : widget.onCancel,
                    style: OutlinedButton.styleFrom(
                      side: BorderSide(color: c.border),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    child: Text(S.of(context).cancel,
                        style: TextStyle(color: c.textSecondary)),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton(
                    onPressed: _loading ? null : _handleConfirm,
                    style: FilledButton.styleFrom(
                      backgroundColor: c.primary,
                      disabledBackgroundColor: c.primary.withValues(alpha: 0.5),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    child: _loading
                        ? const SizedBox(
                            width: 18, height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation(Colors.white),
                            ))
                        : Text(S.of(context).confirmEnable,
                            style: const TextStyle(color: Colors.white)),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  bool _hasTradeAction() {
    final actions = widget.strategy['actions'] as List?;
    if (actions == null) return false;
    return actions.any((a) {
      final type = (a as Map<String, dynamic>?)?['type'] as String?;
      return type == 'buy' || type == 'sell';
    });
  }

  Widget _paramRow(
      AppColorScheme c, String label, String value, IconData icon, Color color) {
    return Row(
      children: [
        Icon(icon, size: 14, color: color),
        const SizedBox(width: 6),
        Text(label, style: TextStyle(color: c.textSecondary, fontSize: 12)),
        const Spacer(),
        Text(value, style: TextStyle(
            color: c.textPrimary, fontSize: 13, fontWeight: FontWeight.w600)),
      ],
    );
  }

  Widget _slider(AppColorScheme c, String label, double value,
      double min, double max, ValueChanged<double> onChanged, String suffix) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: [
          SizedBox(
            width: 52,
            child: Text(label,
                style: TextStyle(color: c.textSecondary, fontSize: 11)),
          ),
          Expanded(
            child: SliderTheme(
              data: SliderThemeData(
                trackHeight: 2,
                thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
                activeTrackColor: c.primary,
                inactiveTrackColor: c.border,
                thumbColor: c.primary,
                overlayShape: const RoundSliderOverlayShape(overlayRadius: 12),
              ),
              child: Slider(
                value: value.clamp(min, max),
                min: min,
                max: max,
                onChanged: onChanged,
              ),
            ),
          ),
          GestureDetector(
            onTap: () => _showValueEditor(c, label, value, min, max, onChanged, suffix),
            child: Container(
              width: 68,
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
              decoration: BoxDecoration(
                color: c.surfaceAlt,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: c.border, width: 0.5),
              ),
              child: Text(
                suffix == '%'
                    ? '${value.toStringAsFixed(value < 1 ? 1 : 0)}$suffix'
                    : '${value.toStringAsFixed(4)}$suffix',
                textAlign: TextAlign.right,
                style: TextStyle(
                    color: c.primary, fontSize: 11, fontWeight: FontWeight.w600),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showValueEditor(AppColorScheme c, String label, double current,
      double min, double max, ValueChanged<double> onChanged, String suffix) {
    final controller = TextEditingController(
      text: suffix == '%'
          ? current.toStringAsFixed(current < 1 ? 1 : 0)
          : current.toStringAsFixed(4),
    );
    showDialog(
      context: context,
      barrierColor: Colors.black87,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1A1F2E),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(label, style: TextStyle(color: c.textPrimary, fontSize: 15)),
        content: TextField(
          controller: controller,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          autofocus: true,
          style: TextStyle(color: c.textPrimary, fontSize: 16),
          decoration: InputDecoration(
            suffixText: suffix.trim(),
            suffixStyle: TextStyle(color: c.textSecondary, fontSize: 14),
            hintText: '${min.toStringAsFixed(suffix == '%' ? 0 : 4)} - ${max.toStringAsFixed(suffix == '%' ? 0 : 4)}',
            hintStyle: TextStyle(color: c.textTertiary, fontSize: 13),
            enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: c.border)),
            focusedBorder: UnderlineInputBorder(borderSide: BorderSide(color: c.primary)),
          ),
          onSubmitted: (v) {
            final parsed = double.tryParse(v);
            if (parsed != null) {
              onChanged(parsed.clamp(min, max));
            }
            Navigator.of(ctx).pop();
          },
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(S.of(context).cancel, style: TextStyle(color: c.textTertiary)),
          ),
          TextButton(
            onPressed: () {
              final parsed = double.tryParse(controller.text);
              if (parsed != null) {
                onChanged(parsed.clamp(min, max));
              }
              Navigator.of(ctx).pop();
            },
            child: Text('OK', style: TextStyle(color: c.primary)),
          ),
        ],
      ),
    );
  }
}

class _ChatInput extends StatelessWidget {
  final TextEditingController controller;
  final bool enabled;
  final VoidCallback onSend;
  const _ChatInput({
    required this.controller,
    required this.enabled,
    required this.onSend,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      decoration: BoxDecoration(
        color: c.cardGlass,
        border: Border(top: BorderSide(color: c.glassBorder, width: 0.5)),
      ),
      padding: EdgeInsets.fromLTRB(
        16, 10, 16,
        MediaQuery.of(context).padding.bottom + 80,
      ),
      child: Row(
        children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: c.surfaceAlt,
                borderRadius: BorderRadius.circular(24),
              ),
              child: TextField(
                controller: controller,
                enabled: enabled,
                maxLines: 3,
                minLines: 1,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => onSend(),
                decoration: InputDecoration(
                  hintText: S.of(context).describeStrategy,
                  hintStyle: TextStyle(color: c.textTertiary, fontSize: 14),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  border: InputBorder.none,
                ),
                style: TextStyle(color: c.textPrimary, fontSize: 14),
              ),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: enabled ? onSend : null,
            child: Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: enabled ? c.primary : c.primaryLight,
                borderRadius: BorderRadius.circular(22),
              ),
              child: Icon(Icons.send_rounded,
                  color: enabled ? Colors.white : c.primary, size: 20),
            ),
          ),
        ],
      ),
    );
  }
}

// ══════════════════════════════════════════════════════
// Tab 2: 我的策略
// ══════════════════════════════════════════════════════
class _MyStrategiesTab extends StatefulWidget {
  const _MyStrategiesTab();

  @override
  State<_MyStrategiesTab> createState() => _MyStrategiesTabState();
}

class _MyStrategiesTabState extends State<_MyStrategiesTab>
    with AutomaticKeepAliveClientMixin {
  List<AgentStrategy>? _strategies;
  bool _loading = true;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _loadStrategies();
  }

  Future<void> _loadStrategies() async {
    final list = await AgentService.instance.listStrategies();
    if (!mounted) return;
    setState(() {
      _strategies = list;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    super.build(context); // AutomaticKeepAliveClientMixin 要求
    final c = context.colors;

    if (_loading) {
      return Center(child: CircularProgressIndicator(color: c.primary));
    }

    if (_strategies == null || _strategies!.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  color: c.primaryLight,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Icon(Icons.auto_graph_rounded,
                    color: c.primary, size: 36),
              ),
              const SizedBox(height: 20),
              Text(S.of(context).noSignals,
                  style: TextStyle(
                    color: c.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  )),
              const SizedBox(height: 10),
              Text(
                S.of(context).whenTokenAppears,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: c.textSecondary,
                  fontSize: 14,
                  height: 1.6,
                ),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadStrategies,
      child: ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: _strategies!.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (ctx, i) {
          final s = _strategies![i];
          return _StrategyCard(
            key: ValueKey(s.id),
            strategy: s,
            onTap: () => Navigator.push(ctx, MaterialPageRoute(builder: (_) => StrategyDetailPage(strategy: s))),
            onToggle: () async {
              final newStatus = s.isActive ? 'paused' : 'active';

              // 暂停 → 激活时弹出风险确认弹窗
              if (newStatus == 'active') {
                final c = ctx.colors;
                final confirmed = await showDialog<bool>(
                  context: ctx,
                  builder: (dialogCtx) => AlertDialog(
                    backgroundColor: c.bgSecondary,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16)),
                    title: Row(
                      children: [
                        Icon(Icons.play_circle_outline_rounded,
                            color: c.primary, size: 22),
                        const SizedBox(width: 8),
                        Text(
                          S.of(dialogCtx).confirmEnableStrategy,
                          style: TextStyle(
                            color: c.textPrimary,
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                    content: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // 策略名称提示
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 8),
                          decoration: BoxDecoration(
                            color: c.primaryLight,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            '\u300C${s.name}\u300D',
                            style: TextStyle(
                              color: c.primary,
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          S.of(dialogCtx).aboutToEnable,
                          style: TextStyle(
                            color: c.textPrimary,
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 10),
                        // 风险条目
                        _agentDisclaimerItem(c, S.of(dialogCtx).paramSetByYou),
                        _agentDisclaimerItem(c, S.of(dialogCtx).understandRisk,
                            isWarning: true),
                        _agentDisclaimerItem(
                            c, S.of(dialogCtx).platformExecuteOnly,
                            isWarning: true),
                      ],
                    ),
                    actions: [
                      TextButton(
                        onPressed: () =>
                            Navigator.pop(dialogCtx, false),
                        child: Text(S.of(dialogCtx).cancel,
                            style: TextStyle(color: c.textTertiary)),
                      ),
                      FilledButton(
                        onPressed: () =>
                            Navigator.pop(dialogCtx, true),
                        style: FilledButton.styleFrom(
                          backgroundColor: c.primary,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10),
                          ),
                        ),
                        child: Text(S.of(dialogCtx).confirmEnable),
                      ),
                    ],
                  ),
                );
                if (confirmed != true) return; // 用户取消，不执行
              }

              final ok = await AgentService.instance
                  .updateStrategyStatus(s.id, newStatus);
              if (!mounted) return;
              if (ok) {
                _loadStrategies();
              } else {
                ScaffoldMessenger.of(ctx).showSnackBar(
                  SnackBar(content: Text(S.of(ctx).loadFailed)),
                );
              }
            },
            onDelete: () async {
              final confirmed = await showDialog<bool>(
                context: ctx,
                barrierColor: Colors.black87,
                builder: (dialogCtx) => AlertDialog(
                  backgroundColor: const Color(0xFF1A1F2E),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  title: Text(S.of(dialogCtx).delete, style: const TextStyle(color: Colors.white, fontSize: 16)),
                  content: Text('确定删除策略 "${s.name}" 吗？删除后不可恢复。',
                      style: const TextStyle(color: Colors.white70, fontSize: 14)),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(dialogCtx, false),
                      child: Text(S.of(dialogCtx).cancel, style: const TextStyle(color: Colors.white54)),
                    ),
                    TextButton(
                      onPressed: () => Navigator.pop(dialogCtx, true),
                      style: TextButton.styleFrom(foregroundColor: Colors.red),
                      child: Text(S.of(dialogCtx).delete),
                    ),
                  ],
                ),
              );
              if (confirmed == true) {
                final ok = await AgentService.instance.deleteStrategy(s.id);
                if (!mounted) return;
                if (ok) {
                  _loadStrategies();
                } else {
                  ScaffoldMessenger.of(ctx).showSnackBar(
                    SnackBar(content: Text(S.of(ctx).loadFailed)),
                  );
                }
              }
            },
          );
        },
      ),
    );
  }
}

class _StrategyCard extends StatefulWidget {
  final AgentStrategy strategy;
  final VoidCallback onTap;
  final VoidCallback onToggle;
  final VoidCallback onDelete;
  const _StrategyCard({
    super.key,
    required this.strategy,
    required this.onTap,
    required this.onToggle,
    required this.onDelete,
  });

  @override
  State<_StrategyCard> createState() => _StrategyCardState();
}

class _StrategyCardState extends State<_StrategyCard> {
  ExecutionSummary? _summary;

  @override
  void initState() {
    super.initState();
    _loadSummary();
  }

  Future<void> _loadSummary() async {
    final resp = await AgentService.instance
        .listExecutions(widget.strategy.id, limit: 200);
    if (!mounted) return;
    if (resp != null) {
      setState(() => _summary = resp.summary);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final s = widget.strategy;
    final isActive = s.isActive;

    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        widget.onTap();
      },
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: c.cardGlass,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isActive ? c.primary.withValues(alpha: 0.3) : c.glassBorder,
            width: 0.5,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── 第1行: 状态 + 名称 + 操作按钮 ──
            Row(
              children: [
                Container(
                  width: 8, height: 8,
                  decoration: BoxDecoration(
                    color: isActive ? c.success : c.textTertiary,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(s.name,
                      style: TextStyle(
                        color: c.textPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                      )),
                ),
                GestureDetector(
                  onTap: widget.onToggle,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: isActive ? c.warningLight : c.successLight,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      isActive ? S.of(context).paused : S.of(context).running,
                      style: TextStyle(
                        color: isActive ? c.warning : c.success,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                GestureDetector(
                  onTap: widget.onDelete,
                  child: Icon(Icons.delete_outline, color: c.danger, size: 18),
                ),
              ],
            ),

            // ── 第2行: 描述 ──
            if (s.description != null) ...[
              const SizedBox(height: 6),
              Text(s.description!,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: c.textSecondary,
                    fontSize: 12,
                    height: 1.4,
                  )),
            ],

            const SizedBox(height: 8),

            // ── 第3行: 触发 + 冷却 + 数据源 ──
            Row(
              children: [
                Icon(Icons.bolt, size: 12, color: c.textTertiary),
                const SizedBox(width: 3),
                Text(S.of(context).triggerInfo(s.triggerCount, s.cooldownMin),
                    style: TextStyle(color: c.textTertiary, fontSize: 11)),
                const Spacer(),
                ...s.dataSources.take(2).map((ds) => Padding(
                      padding: const EdgeInsets.only(left: 4),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: c.primaryLight,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(_dsLabel(ds),
                            style: TextStyle(color: c.primary, fontSize: 10)),
                      ),
                    )),
              ],
            ),

            // ── 第4行: P&L 摘要 (有交易记录时显示) ──
            if (_summary != null && _summary!.hasTrades) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: c.surfaceAlt,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.candlestick_chart_outlined,
                        size: 14, color: c.textTertiary),
                    const SizedBox(width: 6),
                    Text(
                      S.of(context).txCount(_summary!.totalCount),
                      style: TextStyle(
                        color: c.textSecondary,
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const Spacer(),
                    // P&L 值
                    Text(
                      '${_summary!.isProfit ? "+" : ""}\$${_summary!.realizedPnl.abs().toStringAsFixed(2)}',
                      style: TextStyle(
                        color: _summary!.isProfit ? c.success : c.danger,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Icon(Icons.chevron_right_rounded,
                        size: 16, color: c.textTertiary),
                  ],
                ),
              ),
            ] else if (_summary == null) ...[
              // 加载中状态（微妙的占位）
            ] else ...[
              // 无交易时显示一行引导
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(Icons.swap_vert_rounded,
                      size: 12, color: c.textTertiary),
                  const SizedBox(width: 4),
                  Text(
                    S.of(context).noTradeRecords,
                    style: TextStyle(
                      color: c.textTertiary,
                      fontSize: 11,
                    ),
                  ),
                  const Spacer(),
                  Icon(Icons.chevron_right_rounded,
                      size: 16, color: c.textTertiary),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _dsLabel(String ds) {
    switch (ds) {
      case 'pump_tokens':
        return 'Pump';
      case 'hot_coins':
        return S.of(context).hotCoins;
      case 'kol_mentions':
        return 'KOL';
      case 'kol_signals':
        return 'KOL+';
      default:
        return ds;
    }
  }
}

// ══════════════════════════════════════════════════════
// Tab 3: 数据源
// ══════════════════════════════════════════════════════
class _DataSourcesTab extends StatelessWidget {
  const _DataSourcesTab();

  List<({IconData icon, String name, String desc, String status, bool ready})> _sources(BuildContext context) => [
    (
      icon: Icons.rocket_launch_rounded,
      name: 'pump.fun',
      desc: S.of(context).pumpFunSource,
      status: S.of(context).pumpFunStatus,
      ready: true,
    ),
    (
      icon: Icons.local_fire_department_rounded,
      name: S.of(context).multiChainHot,
      desc: S.of(context).multiChainHotDesc,
      status: S.of(context).connected,
      ready: true,
    ),
    (
      icon: Icons.people_alt_rounded,
      name: S.of(context).kolSentiment,
      desc: S.of(context).kolSentimentDesc,
      status: S.of(context).connected,
      ready: true,
    ),
    (
      icon: Icons.account_balance_wallet_rounded,
      name: S.of(context).smartMoneySource,
      desc: S.of(context).smartMoneySourceDesc,
      status: S.of(context).connected,
      ready: true,
    ),
    (
      icon: Icons.currency_exchange_rounded,
      name: 'OKX DEX v6',
      desc: S.of(context).okxDexDesc,
      status: S.of(context).connected,
      ready: true,
    ),
    (
      icon: Icons.show_chart_rounded,
      name: 'CoinGecko',
      desc: S.of(context).coinGeckoDesc,
      status: S.of(context).connected,
      ready: true,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final sources = _sources(context);
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: sources.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (ctx, i) {
        final s = sources[i];
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: c.cardGlass,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: s.ready
                  ? c.primary.withValues(alpha: 0.2)
                  : c.glassBorder,
              width: 0.5,
            ),
          ),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: s.ready ? c.primaryLight : c.surfaceAlt,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(s.icon,
                    color: s.ready ? c.primary : c.textTertiary, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(s.name,
                        style: TextStyle(
                          color: c.textPrimary,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        )),
                    const SizedBox(height: 3),
                    Text(s.desc,
                        style: TextStyle(
                          color: c.textSecondary,
                          fontSize: 12,
                          height: 1.4,
                        )),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: s.ready ? c.successLight : c.surfaceAlt,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  s.status,
                  style: TextStyle(
                    color: s.ready ? c.success : c.textTertiary,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
