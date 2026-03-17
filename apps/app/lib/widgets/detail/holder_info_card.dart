import 'package:flutter/material.dart';
import '../../l10n/app_localizations.dart';
import '../../models/token_detail.dart';
import '../../models/goplus_report.dart';
import '../../theme/app_colors.dart';

/// 持有者信息 — 带颜色阈值
class HolderInfoCard extends StatelessWidget {
  final TokenDetail token;
  final GoPlusReport? goplus;
  final double? top1Pct;
  final bool embedded;

  const HolderInfoCard({super.key, required this.token, this.goplus, this.top1Pct, this.embedded = false});

  @override
  Widget build(BuildContext context) {
    final holders = goplus?.holderCount ?? token.holderCount;
    final top10 = goplus?.top10HolderPct ?? token.top10HolderPct;
    final top1 = top1Pct ?? token.top1HolderPct;

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(S.of(context).holders,
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600,
                color: context.colors.textPrimary)),
        const SizedBox(height: 14),
        Row(
          children: [
            _Stat(label: S.of(context).holderCount, value: _fmtCount(holders), color: context.colors.textPrimary),
            if (top10 != null)
              _Stat(label: S.of(context).top10Ratio, value: '${top10.toStringAsFixed(1)}%',
                  color: _pctColor(context, top10)),
            if (top1 != null)
              _Stat(label: S.of(context).top1Ratio, value: '${top1.toStringAsFixed(1)}%',
                  color: _pctColor(context, top1)),
          ],
        ),
        if (top10 != null) ...[
          const SizedBox(height: 12),
          // 集中度可视化条
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: SizedBox(
              height: 6,
              child: Row(
                children: [
                  Expanded(
                    flex: (top10 * 10).round().clamp(1, 999),
                    child: Container(color: _pctColor(context, top10)),
                  ),
                  Expanded(
                    flex: ((100 - top10) * 10).round().clamp(1, 999),
                    child: Container(color: context.colors.bg),
                  ),
                ],
              ),
            ),
          ),
        ],
      ],
    );

    if (embedded) return content;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(color: Color(0x0A000000), blurRadius: 10, offset: Offset(0, 2)),
        ],
      ),
      child: content,
    );
  }

  Color _pctColor(BuildContext context, double pct) {
    if (pct > 60) return context.colors.danger;
    if (pct > 30) return context.colors.warning;
    return context.colors.success;
  }

  String _fmtCount(int n) {
    if (n >= 10000) return '${(n / 1000).toStringAsFixed(1)}K';
    return n.toString();
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _Stat({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(fontSize: 11, color: context.colors.textSecondary)),
          const SizedBox(height: 4),
          Text(value, style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: color)),
        ],
      ),
    );
  }
}
