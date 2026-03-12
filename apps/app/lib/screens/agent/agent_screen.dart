import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';
import '../../services/agent_service.dart';

/// Agent 策略中心 — 对话 + 策略管理 + 数据源
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
              'Agent 策略',
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
              tabs: const [
                Tab(text: '策略对话'),
                Tab(text: '我的策略'),
                Tab(text: '数据源'),
              ],
            ),
          ),
        ],
        body: TabBarView(
          controller: _tab,
          children: const [
            _ChatTab(),
            _MyStrategiesTab(),
            _DataSourcesTab(),
          ],
        ),
      ),
    );
  }
}

// ══════════════════════════════════════════════════════
// Tab 1: 策略对话（AI 对话窗口）
// ══════════════════════════════════════════════════════

class _ChatTab extends StatefulWidget {
  const _ChatTab();

  @override
  State<_ChatTab> createState() => _ChatTabState();
}

class _ChatTabState extends State<_ChatTab> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final _messages = <_ChatMessage>[];
  bool _sending = false;

  /// 待确认的策略规范
  Map<String, dynamic>? _pendingStrategy;
  String? _pendingPrompt;

  @override
  void initState() {
    super.initState();
    _messages.add(_ChatMessage(
      isUser: false,
      text: '你好！我是你的交易 Agent。\n\n'
          '你可以告诉我你的策略想法，比如：\n'
          '• "帮我找内盘进度 10%-25%、买卖比 > 2 的代币"\n'
          '• "当某代币有3个聪明钱买入时，提醒我"\n'
          '• "监控 KOL 共振信号强度 > 5 的代币"\n\n'
          '我会把你的想法转化为自动化策略。',
    ));
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _sending) return;

    setState(() {
      _messages.add(_ChatMessage(isUser: true, text: text));
      _sending = true;
    });
    _controller.clear();
    _scrollToBottom();

    final response = await AgentService.instance.chat(text);

    if (!mounted) return;

    if (response == null) {
      setState(() {
        _messages.add(_ChatMessage(
          isUser: false,
          text: '网络连接失败，请检查后端服务是否启动。',
        ));
        _sending = false;
      });
    } else {
      setState(() {
        _messages.add(_ChatMessage(isUser: false, text: response.message));
        if (response.requiresConfirmation && response.strategy != null) {
          _pendingStrategy = response.strategy;
          _pendingPrompt = text;
        }
        _sending = false;
      });
    }
    _scrollToBottom();
  }

  Future<void> _confirmStrategy() async {
    if (_pendingStrategy == null) return;
    setState(() => _sending = true);

    final result = await AgentService.instance.createStrategy(
      _pendingStrategy!,
      sourcePrompt: _pendingPrompt,
    );

    if (!mounted) return;
    setState(() {
      if (result != null) {
        _messages.add(_ChatMessage(
          isUser: false,
          text: '策略「${result.name}」已创建并激活！\n'
              '系统将每 30 秒检查条件。\n'
              '可在「我的策略」标签页管理。',
        ));
      } else {
        _messages.add(_ChatMessage(
          isUser: false,
          text: '策略创建失败，请稍后重试。',
        ));
      }
      _pendingStrategy = null;
      _pendingPrompt = null;
      _sending = false;
    });
    _scrollToBottom();
  }

  void _cancelStrategy() {
    setState(() {
      _pendingStrategy = null;
      _pendingPrompt = null;
      _messages.add(_ChatMessage(
        isUser: false,
        text: '已取消。你可以继续描述其他策略想法。',
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
    return Column(
      children: [
        Expanded(
          child: ListView.builder(
            controller: _scrollController,
            padding: const EdgeInsets.all(16),
            itemCount: _messages.length +
                (_pendingStrategy != null ? 1 : 0) +
                (_sending ? 1 : 0),
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
              if (_pendingStrategy != null && i == _messages.length) {
                return _ConfirmCard(
                  strategy: _pendingStrategy!,
                  onConfirm: _confirmStrategy,
                  onCancel: _cancelStrategy,
                );
              }
              return const _TypingIndicator();
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
  const _ChatMessage({required this.isUser, required this.text});
}

class _AiBubble extends StatelessWidget {
  final String text;
  const _AiBubble({required this.text});

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
            child: Text(
              text,
              style: TextStyle(
                color: c.textPrimary,
                fontSize: 14,
                height: 1.6,
              ),
            ),
          ),
        ),
      ],
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

/// 策略确认卡片
class _ConfirmCard extends StatelessWidget {
  final Map<String, dynamic> strategy;
  final VoidCallback onConfirm;
  final VoidCallback onCancel;
  const _ConfirmCard({
    required this.strategy,
    required this.onConfirm,
    required this.onCancel,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final name = strategy['name'] as String? ?? '未命名策略';
    final desc = strategy['description'] as String? ?? '';
    final cooldown = strategy['cooldown_minutes'] as int? ?? 30;

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
                    color: c.textSecondary,
                    fontSize: 13,
                    height: 1.4,
                  )),
            ],
            const SizedBox(height: 4),
            Text('冷却时间: $cooldown分钟',
                style: TextStyle(color: c.textTertiary, fontSize: 12)),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: onCancel,
                    style: OutlinedButton.styleFrom(
                      side: BorderSide(color: c.border),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    child: Text('取消',
                        style: TextStyle(color: c.textSecondary)),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton(
                    onPressed: onConfirm,
                    style: FilledButton.styleFrom(
                      backgroundColor: c.primary,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    child: const Text('创建策略',
                        style: TextStyle(color: Colors.white)),
                  ),
                ),
              ],
            ),
          ],
        ),
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
        MediaQuery.of(context).padding.bottom + 80, // 安全区 + 浮动导航栏高度
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
                  hintText: '描述你的策略想法...',
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

class _MyStrategiesTabState extends State<_MyStrategiesTab> {
  List<AgentStrategy>? _strategies;
  bool _loading = true;

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
              Text('还没有策略',
                  style: TextStyle(
                    color: c.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  )),
              const SizedBox(height: 10),
              Text(
                '通过对话窗口描述你的策略\nAI 会帮你生成、命名并激活',
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
            strategy: s,
            onToggle: () async {
              final newStatus = s.isActive ? 'paused' : 'active';
              await AgentService.instance
                  .updateStrategyStatus(s.id, newStatus);
              _loadStrategies();
            },
            onDelete: () async {
              await AgentService.instance.deleteStrategy(s.id);
              _loadStrategies();
            },
          );
        },
      ),
    );
  }
}

class _StrategyCard extends StatelessWidget {
  final AgentStrategy strategy;
  final VoidCallback onToggle;
  final VoidCallback onDelete;
  const _StrategyCard({
    required this.strategy,
    required this.onToggle,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final isActive = strategy.isActive;

    return Container(
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
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: isActive ? c.success : c.textTertiary,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(strategy.name,
                    style: TextStyle(
                      color: c.textPrimary,
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    )),
              ),
              GestureDetector(
                onTap: onToggle,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: isActive ? c.warningLight : c.successLight,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    isActive ? '暂停' : '恢复',
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
                onTap: onDelete,
                child: Icon(Icons.delete_outline, color: c.danger, size: 18),
              ),
            ],
          ),
          if (strategy.description != null) ...[
            const SizedBox(height: 6),
            Text(strategy.description!,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: c.textSecondary,
                  fontSize: 12,
                  height: 1.4,
                )),
          ],
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(Icons.bolt, size: 12, color: c.textTertiary),
              const SizedBox(width: 3),
              Text('${strategy.triggerCount}次触发', // ignore: unnecessary_brace_in_string_interps
                  style: TextStyle(color: c.textTertiary, fontSize: 11)),
              const SizedBox(width: 8),
              Icon(Icons.timer, size: 12, color: c.textTertiary),
              const SizedBox(width: 3),
              Text('${strategy.cooldownMin}分钟冷却',
                  style: TextStyle(color: c.textTertiary, fontSize: 11)),
              const Spacer(),
              ...strategy.dataSources.take(2).map((ds) => Padding(
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
        ],
      ),
    );
  }

  String _dsLabel(String ds) {
    switch (ds) {
      case 'pump_tokens':
        return '内盘';
      case 'hot_coins':
        return '热币';
      case 'kol_mentions':
        return 'KOL';
      case 'kol_signals':
        return '共振';
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

  static const _sources = [
    (
      icon: Icons.rocket_launch_rounded,
      name: 'pump.fun',
      desc: '内盘实时 WebSocket + REST，BC进度、交易流、毕业事件',
      status: '采集中',
      ready: true,
    ),
    (
      icon: Icons.local_fire_department_rounded,
      name: '多链热币',
      desc: 'SOL/BSC/Base/ETH 四链热币扫描，每2小时更新',
      status: '已接入',
      ready: true,
    ),
    (
      icon: Icons.people_alt_rounded,
      name: 'KOL 舆情',
      desc: '212个 Twitter KOL 监控，共振信号检测，情绪分析',
      status: '已接入',
      ready: true,
    ),
    (
      icon: Icons.account_balance_wallet_rounded,
      name: '聪明钱',
      desc: '多维度分层（Elite/Verified/Watching），60天衰减，Bot检测',
      status: '已接入',
      ready: true,
    ),
    (
      icon: Icons.currency_exchange_rounded,
      name: 'OKX DEX v6',
      desc: '30条链，实时报价 + 执行引擎，支持自动交易',
      status: '已接入',
      ready: true,
    ),
    (
      icon: Icons.show_chart_rounded,
      name: 'CoinGecko',
      desc: 'ATH/ATL、总供应量、社区数据等补充信息',
      status: '已接入',
      ready: true,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: _sources.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (ctx, i) {
        final s = _sources[i];
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
