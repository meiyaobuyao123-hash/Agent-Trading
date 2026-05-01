// 记忆管理页 — Semantic Memory 规则的查看 / 启用-禁用 / 删除 / Shadow 状态
// 引用 docs/agent-pm/06-memory-spec.md §3.3
// 引用 docs/agent-pm/05-tool-catalog.md T11 approve_rule
// 引用 docs/agent-pm/17-tech-plan.md Phase 3
//
// MOCK_MODE:后端 endpoint 暂未实施,AgentService.listSemanticRules 返回 mock
//
// UI:
//   顶部:统计条(active/shadow/dormant 数量)
//   中间:规则列表卡片(按状态分组)
//   每张卡:规则文字 + 状态徽章 + 证据 chip + 操作按钮(启用/禁用/删除)
//   Shadow:14d 倒计时进度条
//   Dormant:30d 未匹配提示

import 'package:flutter/material.dart';
import '../../models/semantic_rule.dart';
import '../../services/agent_service.dart';

class MemoryManagementPage extends StatefulWidget {
  const MemoryManagementPage({super.key});

  @override
  State<MemoryManagementPage> createState() => _MemoryManagementPageState();
}

class _MemoryManagementPageState extends State<MemoryManagementPage> {
  List<SemanticRule> _rules = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final rules = await AgentService.instance.listSemanticRules();
    if (!mounted) return;
    setState(() {
      _rules = rules;
      _loading = false;
    });
  }

  Map<RuleStatus, int> _statusCount() {
    final m = <RuleStatus, int>{};
    for (final r in _rules) {
      m[r.status] = (m[r.status] ?? 0) + 1;
    }
    return m;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('我的规则与记忆'),
        actions: [
          IconButton(
            icon: const Icon(Icons.help_outline),
            onPressed: _showHelp,
            tooltip: '说明',
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _rules.isEmpty
              ? const _EmptyState()
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
                    children: [
                      _StatsBar(statusCount: _statusCount(), total: _rules.length),
                      const SizedBox(height: 12),
                      ..._rules.map((r) => _RuleCard(
                            rule: r,
                            onToggle: () => _toggle(r),
                            onDelete: () => _confirmDelete(r),
                          )),
                    ],
                  ),
                ),
    );
  }

  Future<void> _toggle(SemanticRule r) async {
    final newEnabled = r.status != RuleStatus.active;
    final ok = await AgentService.instance
        .updateRule(r.ruleId, enabled: newEnabled);
    if (!mounted) return;
    if (ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(newEnabled ? '已启用规则' : '已禁用规则')),
      );
      _load();
    }
  }

  Future<void> _confirmDelete(SemanticRule r) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除规则?'),
        content: Text('"${r.humanReadable}"\n\n删除后不可恢复。'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('删除'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    final success = await AgentService.instance.deleteRule(r.ruleId);
    if (!mounted) return;
    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('已删除')),
      );
      _load();
    }
  }

  void _showHelp() {
    showModalBottomSheet<void>(
      context: context,
      builder: (_) => const _HelpSheet(),
    );
  }
}

class _StatsBar extends StatelessWidget {
  final Map<RuleStatus, int> statusCount;
  final int total;
  const _StatsBar({required this.statusCount, required this.total});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    Widget cell(String label, int count, Color color) {
      return Expanded(
        child: Column(
          children: [
            Text('$count',
                style: TextStyle(
                    fontSize: 18, fontWeight: FontWeight.w700, color: color)),
            const SizedBox(height: 2),
            Text(label,
                style: TextStyle(
                    fontSize: 11,
                    color: scheme.onSurface.withValues(alpha: 0.6))),
          ],
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: _cardDecoration(scheme),
      child: Row(
        children: [
          cell('总规则', total, scheme.onSurface),
          cell('Active', statusCount[RuleStatus.active] ?? 0, Colors.green),
          cell('Shadow', statusCount[RuleStatus.shadow] ?? 0, Colors.amber),
          cell('Dormant', statusCount[RuleStatus.dormant] ?? 0,
              scheme.onSurface.withValues(alpha: 0.4)),
        ],
      ),
    );
  }
}

class _RuleCard extends StatelessWidget {
  final SemanticRule rule;
  final VoidCallback onToggle;
  final VoidCallback onDelete;
  const _RuleCard({
    required this.rule,
    required this.onToggle,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: _cardDecoration(scheme),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _StatusBadge(status: rule.status, isShadow: rule.isShadowMode),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  rule.humanReadable,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    height: 1.4,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          // Shadow mode 倒计时
          if (rule.isShadowMode && rule.shadowRemaining != null)
            _ShadowBar(remaining: rule.shadowRemaining!),
          // Dormant 提示
          if (rule.isDormant && rule.dormantSince != null)
            _DormantBanner(since: rule.dormantSince!),
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              _chip('n=${rule.evidence.sampleSize}', scheme),
              _chip(
                  '胜率 ${rule.evidence.winRateDiff >= 0 ? '+' : ''}${rule.evidence.winRateDiff.toStringAsFixed(1)}pp',
                  scheme,
                  color: rule.evidence.winRateDiff >= 0
                      ? Colors.green
                      : Colors.red),
              _chip('match ${rule.matchCount}', scheme),
              if (rule.evidence.wilsonCiLower != null)
                _chip(
                    'Wilson ≥ ${rule.evidence.wilsonCiLower!.toStringAsFixed(2)}',
                    scheme),
              ...rule.activeRegimes.map((r) => _chip(r, scheme, color: scheme.primary)),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  icon: Icon(
                      rule.status == RuleStatus.active
                          ? Icons.pause_circle_outline
                          : Icons.play_circle_outline,
                      size: 16),
                  label: Text(rule.status == RuleStatus.active ? '禁用' : '启用'),
                  onPressed: onToggle,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.delete_outline,
                      size: 16, color: Colors.red),
                  label: const Text('删除', style: TextStyle(color: Colors.red)),
                  style: OutlinedButton.styleFrom(
                    side: BorderSide(color: Colors.red.withValues(alpha: 0.4)),
                  ),
                  onPressed: onDelete,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  static Widget _chip(String text, ColorScheme s, {Color? color}) {
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
}

class _StatusBadge extends StatelessWidget {
  final RuleStatus status;
  final bool isShadow;
  const _StatusBadge({required this.status, required this.isShadow});

  @override
  Widget build(BuildContext context) {
    final (color, label) = _meta();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(label,
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w700,
            color: color,
          )),
    );
  }

  (Color, String) _meta() {
    if (isShadow) return (Colors.amber, 'SHADOW');
    switch (status) {
      case RuleStatus.active:
        return (Colors.green, 'ACTIVE');
      case RuleStatus.shadow:
        return (Colors.amber, 'SHADOW');
      case RuleStatus.dormant:
        return (Colors.grey, 'DORMANT');
      case RuleStatus.disabled:
        return (Colors.orange, 'DISABLED');
      case RuleStatus.archived:
        return (Colors.brown, 'ARCHIVED');
    }
  }
}

class _ShadowBar extends StatelessWidget {
  final Duration remaining;
  const _ShadowBar({required this.remaining});

  @override
  Widget build(BuildContext context) {
    const total = 14 * 24 * 3600; // 14 天秒数
    final remainingSec = remaining.inSeconds.clamp(0, total);
    final progress = 1.0 - remainingSec / total;
    final days = (remainingSec / 86400).ceil();
    return Container(
      padding: const EdgeInsets.all(8),
      margin: const EdgeInsets.only(bottom: 6),
      decoration: BoxDecoration(
        color: Colors.amber.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.visibility, color: Colors.amber, size: 14),
              const SizedBox(width: 4),
              Text('Shadow Mode 观察期',
                  style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: Colors.amber.shade800)),
              const Spacer(),
              Text('剩 $days 天',
                  style: TextStyle(
                      fontSize: 11, color: Colors.amber.shade800)),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 4,
              backgroundColor: Colors.amber.withValues(alpha: 0.2),
              valueColor: const AlwaysStoppedAnimation(Colors.amber),
            ),
          ),
        ],
      ),
    );
  }
}

class _DormantBanner extends StatelessWidget {
  final DateTime since;
  const _DormantBanner({required this.since});

  @override
  Widget build(BuildContext context) {
    final days = DateTime.now().difference(since).inDays;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      margin: const EdgeInsets.only(bottom: 6),
      decoration: BoxDecoration(
        color: Colors.grey.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        children: [
          const Icon(Icons.bedtime_outlined, size: 14, color: Colors.grey),
          const SizedBox(width: 4),
          Expanded(
            child: Text('已休眠 $days 天(30 天未匹配)',
                style: const TextStyle(fontSize: 11, color: Colors.grey)),
          ),
        ],
      ),
    );
  }
}

class _HelpSheet extends StatelessWidget {
  const _HelpSheet();
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('规则状态说明',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          _row('ACTIVE', '生效中,Agent 决策时会用到这条规则', Colors.green),
          _row('SHADOW', '14 天观察期,记录命中但不真正影响决策', Colors.amber),
          _row('DORMANT', '30 天未匹配,自动休眠(可手动重新启用)', Colors.grey),
          _row('DISABLED', '用户手动禁用', Colors.orange),
          const SizedBox(height: 16),
          const Text(
            '为什么要 Shadow:新规则需要 14 天观察确认有效,避免直接上线带来风险。',
            style: TextStyle(fontSize: 12, height: 1.4),
          ),
        ],
      ),
    );
  }

  Widget _row(String tag, String desc, Color color) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.16),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(tag,
              style: TextStyle(
                  fontSize: 10, fontWeight: FontWeight.w700, color: color)),
        ),
        const SizedBox(width: 8),
        Expanded(child: Text(desc, style: const TextStyle(fontSize: 12, height: 1.4))),
      ]),
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
          Icon(Icons.psychology_outlined,
              size: 48, color: Theme.of(context).disabledColor),
          const SizedBox(height: 12),
          const Text('暂无规则,Agent 学习中…'),
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
