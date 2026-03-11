import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';

/// Agent 策略中心
///
/// 规划中的能力：
///   - 对话窗口：通过自然语言描述策略需求
///   - 数据源接入：OKX / 币安 / 社媒数据（Twitter热词/KOL动向）
///   - 策略研发：AI 根据数据帮用户生成、回测交易逻辑
///   - 自动执行：连接用户钱包，按策略自动下单
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
class _ChatTab extends StatelessWidget {
  const _ChatTab();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // 对话区域（占位）
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // AI 开场白
              _AiBubble(
                text: '你好！我是你的交易 Agent。\n\n'
                    '你可以告诉我你的策略想法，比如：\n'
                    '• "帮我找内盘进度 10%-25%、买卖比 > 2 的代币"\n'
                    '• "当某代币有3个聪明钱买入时，自动买入 0.1 SOL"\n'
                    '• "分析今天热币榜 Top5 的共同特征"\n\n'
                    '我会结合 OKX、币安、社媒数据，帮你研发和执行策略。',
              ),
              const SizedBox(height: 24),

              // 功能预告卡片
              const _ComingSoonSection(),
            ],
          ),
        ),

        // 输入框（框架）
        const _ChatInput(),
      ],
    );
  }
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

class _ComingSoonSection extends StatelessWidget {
  const _ComingSoonSection();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Text(
            '即将上线的能力',
            style: TextStyle(
              color: c.textSecondary,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        _FeatureCard(
          icon: Icons.search_rounded,
          title: '策略研发',
          desc: '用自然语言描述你的策略，AI 自动生成过滤规则和打分逻辑',
          tag: '即将上线',
          tagColor: c.primary,
        ),
        const SizedBox(height: 8),
        _FeatureCard(
          icon: Icons.play_arrow_rounded,
          title: '回测验证',
          desc: '用历史数据验证你的策略，查看胜率、回报、最大回撤',
          tag: '即将上线',
          tagColor: c.primary,
        ),
        const SizedBox(height: 8),
        _FeatureCard(
          icon: Icons.flash_on_rounded,
          title: '自动执行',
          desc: '连接钱包后，Agent 按策略条件自动在 pump.fun 内盘买入',
          tag: '规划中',
          tagColor: c.warning,
        ),
        const SizedBox(height: 8),
        _FeatureCard(
          icon: Icons.notifications_active_rounded,
          title: '实时提醒',
          desc: '策略触发时推送通知，支持自定义阈值和条件',
          tag: '规划中',
          tagColor: c.warning,
        ),
      ],
    );
  }
}

class _FeatureCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String desc;
  final String tag;
  final Color tagColor;

  const _FeatureCard({
    required this.icon,
    required this.title,
    required this.desc,
    required this.tag,
    required this.tagColor,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: c.cardGlass,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: c.glassBorder, width: 0.5),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: tagColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: tagColor, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(title,
                      style: TextStyle(
                        color: c.textPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      )),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: tagColor.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(tag,
                        style: TextStyle(color: tagColor, fontSize: 10)),
                    ),
                  ],
                ),
                const SizedBox(height: 3),
                Text(desc,
                  style: TextStyle(
                    color: c.textSecondary,
                    fontSize: 12,
                    height: 1.4,
                  )),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatInput extends StatelessWidget {
  const _ChatInput();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      decoration: BoxDecoration(
        color: c.cardGlass,
        border: Border(top: BorderSide(color: c.glassBorder, width: 0.5)),
      ),
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 20),
      child: Row(
        children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: c.surfaceAlt,
                borderRadius: BorderRadius.circular(24),
              ),
              child: TextField(
                enabled: false,
                decoration: InputDecoration(
                  hintText: '描述你的策略想法... (即将开放)',
                  hintStyle: TextStyle(color: c.textTertiary, fontSize: 14),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  border: InputBorder.none,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: c.primaryLight,
              borderRadius: BorderRadius.circular(22),
            ),
            child: Icon(Icons.send_rounded,
              color: c.primary, size: 20),
          ),
        ],
      ),
    );
  }
}

// ══════════════════════════════════════════════════════
// Tab 2: 我的策略
// ══════════════════════════════════════════════════════
class _MyStrategiesTab extends StatelessWidget {
  const _MyStrategiesTab();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
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
            Text(
              '策略研发中',
              style: TextStyle(
                color: c.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              '通过对话窗口描述你的策略\nAI 会帮你生成、命名并保存\n支持绑定钱包后自动执行',
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
}

// ══════════════════════════════════════════════════════
// Tab 3: 数据源
// ══════════════════════════════════════════════════════
class _DataSourcesTab extends StatelessWidget {
  const _DataSourcesTab();

  static const _sources = [
    (
      icon: Icons.currency_exchange_rounded,
      name: 'OKX DEX v6',
      desc: '30条链，实时报价 + 执行引擎，支持 pump.fun 内盘',
      status: '已接入',
      ready: true,
    ),
    (
      icon: Icons.bar_chart_rounded,
      name: 'Binance Skills',
      desc: '聪明钱信号、市场排名、Meme Rush 热门榜',
      status: '已接入',
      ready: true,
    ),
    (
      icon: Icons.rocket_launch_rounded,
      name: 'pump.fun',
      desc: '内盘实时 WebSocket + REST，BC进度、交易流、毕业事件',
      status: '采集中',
      ready: true,
    ),
    (
      icon: Icons.people_alt_rounded,
      name: '社媒数据',
      desc: 'Twitter KOL 动向、热词监控、舆情信号',
      status: '规划中',
      ready: false,
    ),
    (
      icon: Icons.account_balance_wallet_rounded,
      name: 'Helius / RPC',
      desc: '链上持仓分析、聪明钱地址识别、链上数据核验',
      status: '规划中',
      ready: false,
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
              color: s.ready ? c.primary.withValues(alpha: 0.2) : c.glassBorder,
              width: 0.5,
            ),
          ),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: s.ready
                      ? c.primaryLight
                      : c.surfaceAlt,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(s.icon,
                  color: s.ready ? c.primary : c.textTertiary,
                  size: 22),
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
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: s.ready
                      ? c.successLight
                      : c.surfaceAlt,
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
