import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';
import '../../l10n/app_localizations.dart';

/// 资金流向卡片
/// 显示 24h 净流入/流出 + 大额交易统计 + 买卖力量对比
class FundFlowCard extends StatelessWidget {
  final double buyVolume;
  final double sellVolume;
  final int buyCount;
  final int sellCount;
  final int largeBuyCount;  // 大额买入(>$10K)
  final int largeSellCount; // 大额卖出(>$10K)
  final double largeBuyVolume;
  final double largeSellVolume;
  final bool embedded;

  const FundFlowCard({
    super.key,
    required this.buyVolume,
    required this.sellVolume,
    required this.buyCount,
    required this.sellCount,
    this.largeBuyCount = 0,
    this.largeSellCount = 0,
    this.largeBuyVolume = 0,
    this.largeSellVolume = 0,
    this.embedded = false,
  });

  String _fmtUsd(double v) {
    if (v >= 1e9) return '\$${(v / 1e9).toStringAsFixed(1)}B';
    if (v >= 1e6) return '\$${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '\$${(v / 1e3).toStringAsFixed(1)}K';
    if (v > 0) return '\$${v.toStringAsFixed(0)}';
    return '\$0';
  }

  @override
  Widget build(BuildContext context) {
    final netFlow = buyVolume - sellVolume;
    final totalVolume = buyVolume + sellVolume;
    final buyRatio = totalVolume > 0 ? buyVolume / totalVolume : 0.5;
    final isPositive = netFlow >= 0;

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 标题行
        Padding(
          padding: const EdgeInsets.only(bottom: 14),
          child: Row(
            children: [
              Icon(Icons.swap_vert, size: 18, color: context.colors.textSecondary),
              const SizedBox(width: 6),
              Text(
                S.of(context).fundFlow24h,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: context.colors.textPrimary,
                ),
              ),
            ],
          ),
        ),

        // 净流入大数字
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
          decoration: BoxDecoration(
            color: isPositive
                ? const Color(0xFF22C55E).withValues(alpha: 0.1)
                : const Color(0xFFEF4444).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isPositive
                  ? const Color(0xFF22C55E).withValues(alpha: 0.3)
                  : const Color(0xFFEF4444).withValues(alpha: 0.3),
            ),
          ),
          child: Column(
            children: [
              Text(
                S.of(context).netFlowLabel,
                style: TextStyle(fontSize: 12, color: context.colors.textSecondary),
              ),
              const SizedBox(height: 4),
              Text(
                '${isPositive ? "+" : ""}${_fmtUsd(netFlow.abs())}',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  color: isPositive ? const Color(0xFF22C55E) : const Color(0xFFEF4444),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                isPositive ? S.of(context).netInflow : S.of(context).netOutflow,
                style: TextStyle(
                  fontSize: 12,
                  color: isPositive ? const Color(0xFF22C55E) : const Color(0xFFEF4444),
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 16),

        // 买卖力量条
        Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '${S.of(context).buyPressure} ${(buyRatio * 100).toStringAsFixed(1)}%',
                  style: const TextStyle(fontSize: 12, color: Color(0xFF22C55E)),
                ),
                Text(
                  '${S.of(context).sellPressure} ${((1 - buyRatio) * 100).toStringAsFixed(1)}%',
                  style: const TextStyle(fontSize: 12, color: Color(0xFFEF4444)),
                ),
              ],
            ),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: SizedBox(
                height: 10,
                child: Row(
                  children: [
                    Flexible(
                      flex: (buyRatio * 100).round().clamp(1, 99),
                      child: Container(color: const Color(0xFF22C55E)),
                    ),
                    Flexible(
                      flex: ((1 - buyRatio) * 100).round().clamp(1, 99),
                      child: Container(color: const Color(0xFFEF4444)),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),

        const SizedBox(height: 16),

        // 买入/卖出明细
        Row(
          children: [
            Expanded(child: _flowDetail(
              context,
              S.of(context).totalBuy,
              _fmtUsd(buyVolume),
              '$buyCount ${S.of(context).txCount}',
              const Color(0xFF22C55E),
            )),
            const SizedBox(width: 12),
            Expanded(child: _flowDetail(
              context,
              S.of(context).totalSell,
              _fmtUsd(sellVolume),
              '$sellCount ${S.of(context).txCount}',
              const Color(0xFFEF4444),
            )),
          ],
        ),

        // 大额交易（如果有）
        if (largeBuyCount > 0 || largeSellCount > 0) ...[
          const SizedBox(height: 12),
          Divider(height: 1, color: context.colors.textSecondary.withValues(alpha: 0.2)),
          const SizedBox(height: 12),
          Row(
            children: [
              Icon(Icons.diamond_outlined, size: 14, color: context.colors.textSecondary),
              const SizedBox(width: 4),
              Text(
                S.of(context).largeOrders,
                style: TextStyle(fontSize: 12, color: context.colors.textSecondary),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: _flowDetail(
                context,
                S.of(context).largeBuy,
                _fmtUsd(largeBuyVolume),
                '$largeBuyCount ${S.of(context).txCount}',
                const Color(0xFF22C55E),
              )),
              const SizedBox(width: 12),
              Expanded(child: _flowDetail(
                context,
                S.of(context).largeSell,
                _fmtUsd(largeSellVolume),
                '$largeSellCount ${S.of(context).txCount}',
                const Color(0xFFEF4444),
              )),
            ],
          ),
        ],
      ],
    );

    if (embedded) return content;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(12),
      ),
      child: content,
    );
  }

  Widget _flowDetail(BuildContext context, String label, String value, String sub, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(fontSize: 11, color: context.colors.textSecondary)),
          const SizedBox(height: 4),
          Text(value, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: color)),
          const SizedBox(height: 2),
          Text(sub, style: TextStyle(fontSize: 11, color: context.colors.textSecondary)),
        ],
      ),
    );
  }
}
