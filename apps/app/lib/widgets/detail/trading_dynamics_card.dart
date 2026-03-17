import 'package:flutter/material.dart';
import '../../l10n/app_localizations.dart';
import '../../models/token_detail.dart';
import '../../theme/app_colors.dart';

/// 交易动态 — 买压百分比 + 厚实比例条
class TradingDynamicsCard extends StatelessWidget {
  final TokenDetail token;
  final bool embedded;
  const TradingDynamicsCard({super.key, required this.token, this.embedded = false});

  @override
  Widget build(BuildContext context) {
    final buyPct1h = (token.buySellRatio1h * 100).round();
    final buyPct24h = (token.buySellRatio24h * 100).round();
    final trending = buyPct1h > buyPct24h ? '▲' : buyPct1h < buyPct24h ? '▼' : '';
    final trendColor = buyPct1h > buyPct24h ? context.colors.success : context.colors.danger;

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(S.of(context).tradeDynamics,
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600,
                    color: context.colors.textPrimary)),
            const Spacer(),
            Text(S.of(context).buyPressure(buyPct1h.toString()),
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800,
                    color: buyPct1h >= 50 ? context.colors.success : context.colors.danger)),
            if (trending.isNotEmpty)
              Text(' $trending',
                  style: TextStyle(fontSize: 14, color: trendColor)),
          ],
        ),
        const SizedBox(height: 16),
        _RatioBar(label: '1h', ratio: token.buySellRatio1h,
            buys: token.buys1h, sells: token.sells1h),
        const SizedBox(height: 12),
        _RatioBar(label: '24h', ratio: token.buySellRatio24h,
            buys: token.buys24h, sells: token.sells24h),
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
}

class _RatioBar extends StatelessWidget {
  final String label;
  final double ratio;
  final int buys;
  final int sells;
  const _RatioBar({required this.label, required this.ratio,
    required this.buys, required this.sells});

  @override
  Widget build(BuildContext context) {
    final buyFlex = (ratio * 100).round().clamp(1, 99);
    final sellFlex = (100 - buyFlex).clamp(1, 99);

    return Column(
      children: [
        Row(
          children: [
            SizedBox(width: 30,
              child: Text(label, style: TextStyle(fontSize: 13,
                  fontWeight: FontWeight.w500, color: context.colors.textSecondary))),
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: SizedBox(
                  height: 24,
                  child: Row(
                    children: [
                      Expanded(
                        flex: buyFlex,
                        child: Container(
                          color: context.colors.success,
                          alignment: Alignment.center,
                          child: buyFlex > 15
                              ? Text('$buyFlex%',
                                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700,
                                      color: Colors.white))
                              : null,
                        ),
                      ),
                      Expanded(
                        flex: sellFlex,
                        child: Container(
                          color: context.colors.danger,
                          alignment: Alignment.center,
                          child: sellFlex > 15
                              ? Text('$sellFlex%',
                                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700,
                                      color: Colors.white))
                              : null,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Row(
          children: [
            const SizedBox(width: 30),
            Text(S.of(context).buyLabel(buys.toString()), style: TextStyle(fontSize: 12, color: context.colors.success)),
            const Spacer(),
            Text(S.of(context).sellLabel(sells.toString()), style: TextStyle(fontSize: 12, color: context.colors.danger)),
          ],
        ),
      ],
    );
  }
}
