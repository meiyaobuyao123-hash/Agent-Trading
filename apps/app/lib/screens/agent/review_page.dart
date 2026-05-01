// 复盘报告页 — 日/周/月切换 + 概览 + 洞察 + 规则提议
// 引用 docs/agent-pm/03-prd.md §7.7 Review Schema
// 引用 docs/agent-pm/05-tool-catalog.md S07 review-engine
// 引用 docs/agent-pm/17-tech-plan.md Phase 3
//
// MOCK_MODE:后端 endpoint 暂未实施,AgentService.getReview 返回 mock 数据
// 用户可直接看到 UI(数据用合理占位:BTC/ETH/TRUMP 案例)
//
// 顶部:Period 切换器(日/周/月)
// 中间:Summary 卡 + Metrics 卡 + Insights 列表 + RuleProposals 列表
// 底部:"管理我的记忆" 按钮 → push memory_management_page

import 'package:flutter/material.dart';
import '../../models/review.dart';
import '../../services/agent_service.dart';
import 'memory_management_page.dart';

class ReviewPage extends StatefulWidget {
  const ReviewPage({super.key});

  @override
  State<ReviewPage> createState() => _ReviewPageState();
}

class _ReviewPageState extends State<ReviewPage> {
  String _period = 'daily';
  Review? _review;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final r = await AgentService.instance.getReview(_period);
    if (!mounted) return;
    setState(() {
      _review = r;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('复盘报告'),
      ),
      body: Column(
        children: [
          _PeriodSwitcher(
            current: _period,
            onChange: (p) {
              setState(() => _period = p);
              _load();
            },
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _review == null
                    ? const _EmptyState()
                    : RefreshIndicator(
                        onRefresh: _load,
                        child: _ReviewContent(review: _review!),
                      ),
          ),
        ],
      ),
    );
  }
}

class _PeriodSwitcher extends StatelessWidget {
  final String current;
  final void Function(String) onChange;
  const _PeriodSwitcher({required this.current, required this.onChange});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    Widget btn(String key, String label) {
      final selected = current == key;
      return Expanded(
        child: GestureDetector(
          onTap: () => onChange(key),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
            padding: const EdgeInsets.symmetric(vertical: 10),
            decoration: BoxDecoration(
              color: selected
                  ? scheme.primary.withValues(alpha: 0.16)
                  : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: selected
                    ? scheme.primary
                    : scheme.outline.withValues(alpha: 0.2),
              ),
            ),
            child: Text(
              label,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                color: selected ? scheme.primary : scheme.onSurface,
              ),
            ),
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Row(children: [btn('daily', '日'), btn('weekly', '周'), btn('monthly', '月')]),
    );
  }
}

class _ReviewContent extends StatelessWidget {
  final Review review;
  const _ReviewContent({required this.review});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
      children: [
        _SummaryCard(review: review),
        const SizedBox(height: 12),
        _MetricsCard(metrics: review.metrics),
        const SizedBox(height: 16),
        if (review.insights.isNotEmpty) ...[
          _SectionHeader(title: '洞察 (${review.insights.length})'),
          ...review.insights.map((i) => _InsightCard(insight: i)),
          const SizedBox(height: 16),
        ],
        if (review.ruleProposals.isNotEmpty) ...[
          _SectionHeader(title: '规则提议 (${review.ruleProposals.length})'),
          ...review.ruleProposals.map((p) => _RuleProposalCard(proposal: p)),
          const SizedBox(height: 16),
        ],
        _MemoryNavButton(),
      ],
    );
  }
}

class _SummaryCard extends StatelessWidget {
  final Review review;
  const _SummaryCard({required this.review});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(scheme),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.analytics_outlined, color: scheme.primary, size: 18),
              const SizedBox(width: 6),
              Text(
                '${_periodLabel(review.period)} · ${_dateRange(review)}',
                style: TextStyle(
                  fontSize: 12,
                  color: scheme.onSurface.withValues(alpha: 0.6),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            review.summary.headline,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              height: 1.3,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            review.summary.body,
            style: TextStyle(
              fontSize: 13,
              height: 1.5,
              color: scheme.onSurface.withValues(alpha: 0.8),
            ),
          ),
        ],
      ),
    );
  }

  static String _periodLabel(String p) {
    switch (p) {
      case 'daily':
        return '日报';
      case 'weekly':
        return '周报';
      case 'monthly':
        return '月报';
      default:
        return p;
    }
  }

  static String _dateRange(Review r) {
    String fmt(DateTime d) =>
        '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
    return '${fmt(r.periodFrom)} → ${fmt(r.periodTo)}';
  }
}

class _MetricsCard extends StatelessWidget {
  final ReviewMetrics metrics;
  const _MetricsCard({required this.metrics});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    Widget cell(String label, String value, {Color? color}) {
      return Expanded(
        child: Column(
          children: [
            Text(value,
                style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                    color: color ?? scheme.onSurface)),
            const SizedBox(height: 2),
            Text(label,
                style: TextStyle(
                    fontSize: 11, color: scheme.onSurface.withValues(alpha: 0.6))),
          ],
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _cardDecoration(scheme),
      child: Column(
        children: [
          Row(children: [
            cell('交易', '${metrics.tradeCount}'),
            cell('胜率', '${(metrics.winRate * 100).toStringAsFixed(1)}%',
                color: metrics.winRate >= 0.5 ? Colors.green : Colors.orange),
            cell(
                'EV',
                '${metrics.evPct >= 0 ? '+' : ''}${metrics.evPct.toStringAsFixed(2)}%',
                color: metrics.evPct >= 0 ? Colors.green : Colors.red),
          ]),
          const SizedBox(height: 14),
          Row(children: [
            cell('夏普', metrics.sharpe.toStringAsFixed(2),
                color: metrics.sharpe >= 1.0 ? Colors.green : Colors.orange),
            cell('最大回撤', '${metrics.maxDrawdownPct.toStringAsFixed(1)}%',
                color: Colors.red.withValues(alpha: 0.85)),
            cell('盈亏比', metrics.profitFactor.toStringAsFixed(2),
                color: metrics.profitFactor >= 1.5 ? Colors.green : Colors.orange),
          ]),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 4, 4, 8),
      child: Text(
        title,
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: scheme.onSurface.withValues(alpha: 0.7),
        ),
      ),
    );
  }
}

class _InsightCard extends StatelessWidget {
  final Insight insight;
  const _InsightCard({required this.insight});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (icon, color, label) = _typeMeta(insight.type, scheme);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: _cardDecoration(scheme),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(label,
                          style: TextStyle(
                              fontSize: 10, fontWeight: FontWeight.w600, color: color)),
                    ),
                    if (insight.evidenceTradeIds.isNotEmpty) ...[
                      const SizedBox(width: 6),
                      Text('n=${insight.evidenceTradeIds.length}',
                          style: TextStyle(
                              fontSize: 10,
                              color: scheme.onSurface.withValues(alpha: 0.5))),
                    ],
                    const Spacer(),
                    if (insight.llmJudgeScore != null)
                      Text('judge ${insight.llmJudgeScore!.toStringAsFixed(2)}',
                          style: TextStyle(
                              fontSize: 10,
                              color: scheme.onSurface.withValues(alpha: 0.5))),
                  ],
                ),
                const SizedBox(height: 6),
                Text(insight.text,
                    style: const TextStyle(fontSize: 13, height: 1.4)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  static (IconData, Color, String) _typeMeta(String t, ColorScheme s) {
    switch (t) {
      case 'win_pattern':
        return (Icons.trending_up, Colors.green, '胜势');
      case 'loss_pattern':
        return (Icons.trending_down, Colors.red, '亏损');
      case 'risk_warning':
        return (Icons.warning_amber_rounded, Colors.orange, '风险');
      default:
        return (Icons.info_outline, s.primary, '观察');
    }
  }
}

class _RuleProposalCard extends StatelessWidget {
  final RuleProposal proposal;
  const _RuleProposalCard({required this.proposal});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: _cardDecoration(scheme),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.lightbulb_outline, color: Colors.amber, size: 18),
              const SizedBox(width: 6),
              Expanded(
                child: Text(proposal.humanReadable,
                    style: const TextStyle(
                        fontSize: 13, fontWeight: FontWeight.w600, height: 1.4)),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              _miniChip('n=${proposal.sampleSize}', scheme),
              _miniChip(
                  '胜率 ${proposal.winRateDiff >= 0 ? '+' : ''}${proposal.winRateDiff.toStringAsFixed(1)}pp',
                  scheme,
                  color: proposal.winRateDiff >= 0 ? Colors.green : Colors.red),
              if (proposal.wilsonCiLower != null)
                _miniChip('Wilson ≥ ${proposal.wilsonCiLower!.toStringAsFixed(2)}',
                    scheme),
              ...proposal.activeRegimes
                  .map((r) => _miniChip(r, scheme, color: scheme.primary)),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.preview, size: 16),
                  label: const Text('Dry-run 预览'),
                  onPressed: () => _showDryRunSnack(context, proposal),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton.icon(
                  icon: const Icon(Icons.check, size: 16),
                  label: const Text('采纳'),
                  onPressed: () => _approve(context, proposal),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  static Widget _miniChip(String text, ColorScheme s, {Color? color}) {
    final c = color ?? s.onSurface.withValues(alpha: 0.7);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: c.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(text,
          style: TextStyle(fontSize: 10, fontWeight: FontWeight.w500, color: c)),
    );
  }

  void _showDryRunSnack(BuildContext context, RuleProposal p) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Dry-run: 30 天回溯 ${p.sampleSize} 笔,胜率差 ${p.winRateDiff.toStringAsFixed(1)}pp'),
        duration: const Duration(seconds: 3),
      ),
    );
  }

  Future<void> _approve(BuildContext context, RuleProposal p) async {
    final ok = await AgentService.instance.approveRuleProposal(p.proposalId);
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(ok ? '已采纳,进入 14 天 Shadow Mode' : '采纳失败,稍后重试'),
        backgroundColor: ok ? Colors.green : Colors.red,
      ),
    );
  }
}

class _MemoryNavButton extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(48),
      ),
      icon: const Icon(Icons.memory),
      label: const Text('管理我的规则与记忆'),
      onPressed: () {
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const MemoryManagementPage()),
        );
      },
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.summarize_outlined,
              size: 48, color: Theme.of(context).disabledColor),
          const SizedBox(height: 12),
          const Text('当前周期暂无复盘报告'),
        ],
      ),
    );
  }
}

BoxDecoration _cardDecoration(ColorScheme scheme) => BoxDecoration(
      color: scheme.surface,
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: scheme.outline.withValues(alpha: 0.18)),
    );
