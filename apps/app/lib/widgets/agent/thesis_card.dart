// Thesis 卡片 — 展示 Agent 深度分析输出(S08 thesis-writer)
// 引用 docs/agent-pm/03-prd.md §2.7 Thesis Schema
// 引用 docs/agent-pm/17-tech-plan.md Phase 3
// 引用 lib/models/thesis.dart
// W3 D3 实施

import 'package:flutter/material.dart';
import '../../models/thesis.dart';

class ThesisCard extends StatelessWidget {
  final Thesis thesis;
  const ThesisCard({super.key, required this.thesis});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: scheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: scheme.outline.withValues(alpha: 0.2)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 8, offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 低置信度警告条
          if (thesis.isLowConviction) _LowConvictionBanner(),

          // Header: 代币 + 链 + Level
          _Header(thesis: thesis),
          const SizedBox(height: 12),

          // Direction + Conviction
          _DirectionRow(thesis: thesis),
          const SizedBox(height: 12),

          // Entry / Stop / Target
          if (thesis.entryZone != null || thesis.stopLoss != null)
            _PriceRow(thesis: thesis),
          if (thesis.entryZone != null || thesis.stopLoss != null)
            const SizedBox(height: 12),

          // Summary
          if (thesis.summary30w.isNotEmpty)
            _Summary(text: thesis.summary30w),

          // Risks(必有 ≥ 2 条)
          if (thesis.risks.isNotEmpty) ...[
            const SizedBox(height: 12),
            _RisksSection(risks: thesis.risks),
          ],

          // Evidence(折叠)
          if (thesis.evidence.isNotEmpty) ...[
            const SizedBox(height: 12),
            _EvidenceSection(items: thesis.evidence),
          ],

          // Similar past cases
          if (thesis.similarPastCases.isNotEmpty) ...[
            const SizedBox(height: 12),
            _SimilarCasesSection(cases: thesis.similarPastCases),
          ],

          // Footer: cost + latency
          if (thesis.costUsd != null || thesis.latencyMs != null) ...[
            const SizedBox(height: 12),
            _Footer(thesis: thesis),
          ],
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// 低置信度警告
// ─────────────────────────────────────────────────────────────

class _LowConvictionBanner extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.red.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.red.withValues(alpha: 0.4)),
      ),
      child: Row(children: const [
        Icon(Icons.warning_amber_rounded, size: 18, color: Colors.red),
        SizedBox(width: 8),
        Expanded(
          child: Text(
            '低置信度分析,建议小仓位试水或观望',
            style: TextStyle(color: Colors.red, fontSize: 13),
          ),
        ),
      ]),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Header
// ─────────────────────────────────────────────────────────────

class _Header extends StatelessWidget {
  final Thesis thesis;
  const _Header({required this.thesis});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                thesis.tokenSymbol ?? thesis.tokenAddress.substring(0, 8),
                style: const TextStyle(
                  fontSize: 18, fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                thesis.chain.toUpperCase(),
                style: TextStyle(
                  fontSize: 11,
                  color: scheme.onSurface.withValues(alpha: 0.6),
                ),
              ),
            ],
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: _levelColor(thesis.level).withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: _levelColor(thesis.level)),
          ),
          child: Text(
            thesis.level,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.bold,
              color: _levelColor(thesis.level),
            ),
          ),
        ),
      ],
    );
  }

  Color _levelColor(String level) {
    switch (level) {
      case 'L3': return Colors.purple;
      case 'L2': return Colors.blue;
      case 'L1': return Colors.grey;
      default: return Colors.grey;
    }
  }
}

// ─────────────────────────────────────────────────────────────
// Direction Row(方向 + Conviction)
// ─────────────────────────────────────────────────────────────

class _DirectionRow extends StatelessWidget {
  final Thesis thesis;
  const _DirectionRow({required this.thesis});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final color = _directionColor(thesis.direction);
    return Row(
      children: [
        Icon(_directionIcon(thesis.direction), color: color, size: 24),
        const SizedBox(width: 8),
        Text(
          _directionLabel(thesis.direction),
          style: TextStyle(
            fontSize: 18, fontWeight: FontWeight.bold, color: color,
          ),
        ),
        const Spacer(),
        // Conviction 进度条
        SizedBox(
          width: 80,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '置信 ${(thesis.conviction * 100).toStringAsFixed(0)}%',
                style: TextStyle(
                  fontSize: 11,
                  color: scheme.onSurface.withValues(alpha: 0.7),
                ),
              ),
              const SizedBox(height: 4),
              ClipRRect(
                borderRadius: BorderRadius.circular(2),
                child: LinearProgressIndicator(
                  value: thesis.conviction,
                  minHeight: 4,
                  backgroundColor: scheme.outline.withValues(alpha: 0.2),
                  valueColor: AlwaysStoppedAnimation(color),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Color _directionColor(String dir) {
    switch (dir) {
      case 'bullish': return Colors.green.shade600;
      case 'bearish': return Colors.red.shade600;
      case 'avoid': return Colors.red.shade800;
      case 'hold': return Colors.orange;
      default: return Colors.grey;
    }
  }

  IconData _directionIcon(String dir) {
    switch (dir) {
      case 'bullish': return Icons.trending_up;
      case 'bearish': return Icons.trending_down;
      case 'avoid': return Icons.block;
      case 'hold': return Icons.pause_circle_outline;
      default: return Icons.remove;
    }
  }

  String _directionLabel(String dir) {
    switch (dir) {
      case 'bullish': return '看涨';
      case 'bearish': return '看跌';
      case 'avoid': return '回避';
      case 'hold': return '观望';
      case 'neutral': return '中性';
      default: return dir;
    }
  }
}

// ─────────────────────────────────────────────────────────────
// Price Row(入场区间 / 止损 / 目标价)
// ─────────────────────────────────────────────────────────────

class _PriceRow extends StatelessWidget {
  final Thesis thesis;
  const _PriceRow({required this.thesis});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: _PriceBox(
          label: '入场',
          value: thesis.entryZone == null
              ? '-'
              : '\$${thesis.entryZone!.low.toStringAsFixed(2)}-'
                '${thesis.entryZone!.high.toStringAsFixed(2)}',
          color: Colors.blue,
        )),
        const SizedBox(width: 8),
        Expanded(child: _PriceBox(
          label: '止损',
          value: thesis.stopLoss == null
              ? '-'
              : '\$${thesis.stopLoss!.toStringAsFixed(2)}',
          color: Colors.red,
        )),
        const SizedBox(width: 8),
        Expanded(child: _PriceBox(
          label: '目标',
          value: thesis.targetPrice.isEmpty
              ? '-'
              : '\$${thesis.targetPrice.first.toStringAsFixed(2)}'
                '${thesis.targetPrice.length > 1 ? '+' : ''}',
          color: Colors.green,
        )),
      ],
    );
  }
}

class _PriceBox extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _PriceBox({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          Text(label, style: TextStyle(fontSize: 11, color: color)),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              fontSize: 13, fontWeight: FontWeight.bold, color: color,
            ),
            maxLines: 1, overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Summary
// ─────────────────────────────────────────────────────────────

class _Summary extends StatelessWidget {
  final String text;
  const _Summary({required this.text});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 13, height: 1.4,
          color: scheme.onSurface.withValues(alpha: 0.85),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Risks
// ─────────────────────────────────────────────────────────────

class _RisksSection extends StatelessWidget {
  final List<String> risks;
  const _RisksSection({required this.risks});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: const [
          Icon(Icons.warning_amber_outlined, size: 16, color: Colors.orange),
          SizedBox(width: 4),
          Text('风险', style: TextStyle(
            fontSize: 13, fontWeight: FontWeight.w600,
          )),
        ]),
        const SizedBox(height: 6),
        ...risks.map((r) => Padding(
          padding: const EdgeInsets.only(bottom: 4, left: 4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.only(top: 6),
                child: Icon(Icons.circle, size: 5, color: Colors.orange),
              ),
              const SizedBox(width: 8),
              Expanded(child: Text(r, style: const TextStyle(fontSize: 12, height: 1.4))),
            ],
          ),
        )),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Evidence(折叠)
// ─────────────────────────────────────────────────────────────

class _EvidenceSection extends StatelessWidget {
  final List<EvidenceItem> items;
  const _EvidenceSection({required this.items});

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(left: 8, bottom: 8),
      title: Row(children: [
        const Icon(Icons.fact_check_outlined, size: 16, color: Colors.blueGrey),
        const SizedBox(width: 4),
        Text('证据 (${items.length})',
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
      ]),
      children: items.map((e) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${e.source}: ',
              style: TextStyle(
                fontSize: 11, color: Colors.blueGrey.shade600,
                fontWeight: FontWeight.w500,
              ),
            ),
            Expanded(
              child: Text(e.value, style: const TextStyle(fontSize: 12)),
            ),
          ],
        ),
      )).toList(),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Similar Past Cases(折叠)
// ─────────────────────────────────────────────────────────────

class _SimilarCasesSection extends StatelessWidget {
  final List<SimilarCase> cases;
  const _SimilarCasesSection({required this.cases});

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      title: Row(children: [
        const Icon(Icons.history, size: 16, color: Colors.purple),
        const SizedBox(width: 4),
        Text('历史相似 (${cases.length})',
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
      ]),
      children: cases.map((c) => ListTile(
        dense: true,
        leading: Icon(
          c.outcome == 'win' ? Icons.check_circle : Icons.cancel,
          color: c.outcome == 'win' ? Colors.green : Colors.red, size: 18,
        ),
        title: Text(c.tokenSymbol, style: const TextStyle(fontSize: 12)),
        subtitle: Text(
          '${c.occurredAt.toLocal().toIso8601String().substring(0, 10)} · 相似度 ${(c.similarity * 100).toStringAsFixed(0)}%',
          style: const TextStyle(fontSize: 10),
        ),
      )).toList(),
    );
  }
}

// ─────────────────────────────────────────────────────────────
// Footer(成本 / 延迟)
// ─────────────────────────────────────────────────────────────

class _Footer extends StatelessWidget {
  final Thesis thesis;
  const _Footer({required this.thesis});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      children: [
        if (thesis.costUsd != null) ...[
          Icon(Icons.attach_money, size: 12,
            color: scheme.onSurface.withValues(alpha: 0.5)),
          Text('\$${thesis.costUsd!.toStringAsFixed(3)}',
            style: TextStyle(
              fontSize: 10,
              color: scheme.onSurface.withValues(alpha: 0.5),
            )),
          const SizedBox(width: 12),
        ],
        if (thesis.latencyMs != null) ...[
          Icon(Icons.timer_outlined, size: 12,
            color: scheme.onSurface.withValues(alpha: 0.5)),
          Text(' ${thesis.latencyMs}ms',
            style: TextStyle(
              fontSize: 10,
              color: scheme.onSurface.withValues(alpha: 0.5),
            )),
        ],
      ],
    );
  }
}
