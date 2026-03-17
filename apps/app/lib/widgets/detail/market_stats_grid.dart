import 'package:flutter/material.dart';
import '../../l10n/app_localizations.dart';
import '../../models/token_detail.dart';
import '../../theme/app_colors.dart';

/// 横向紧凑指标行 — 市值/流动性/24h量/1h量/流动性比
class MarketStatsGrid extends StatelessWidget {
  final TokenDetail token;
  const MarketStatsGrid({super.key, required this.token});

  @override
  Widget build(BuildContext context) {
    final liqMcRatio = token.marketCapUsd > 0
        ? (token.liquidityUsd / token.marketCapUsd * 100)
        : 0.0;

    final items = [
      _Item(S.of(context).marketCap, _fmtUsd(token.marketCapUsd)),
      _Item(S.of(context).liquiditySmall, _fmtUsd(token.liquidityUsd)),
      _Item(S.of(context).vol24hShort, _fmtUsd(token.volume24hUsd)),
      _Item(S.of(context).vol1hShort, _fmtUsd(token.volume1hUsd)),
      _Item(S.of(context).liqMcShort, '${liqMcRatio.toStringAsFixed(1)}%'),
    ];

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 14),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(color: Color(0x0A000000), blurRadius: 10, offset: Offset(0, 2)),
        ],
      ),
      child: Row(
        children: List.generate(items.length * 2 - 1, (i) {
          if (i.isOdd) {
            return Container(width: 0.5, height: 30, color: context.colors.divider.withValues(alpha: 0.3));
          }
          final item = items[i ~/ 2];
          return Expanded(
            child: Column(
              children: [
                Text(item.label,
                    style: TextStyle(fontSize: 10, fontWeight: FontWeight.w500,
                        color: context.colors.textSecondary, letterSpacing: 0.5)),
                const SizedBox(height: 4),
                Text(item.value,
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700,
                        color: context.colors.textPrimary)),
              ],
            ),
          );
        }),
      ),
    );
  }

  String _fmtUsd(double v) {
    if (v >= 1e9) return '\$${(v / 1e9).toStringAsFixed(1)}B';
    if (v >= 1e6) return '\$${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '\$${(v / 1e3).toStringAsFixed(0)}K';
    if (v > 0) return '\$${v.toStringAsFixed(0)}';
    return '-';
  }
}

class _Item {
  final String label;
  final String value;
  const _Item(this.label, this.value);
}
