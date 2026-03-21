import 'dart:math';
import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';
import '../../l10n/app_localizations.dart';

/// 交易历史时间线图表
/// 按时段聚合买卖交易，展示买卖分布柱状图
class TradeHistoryChart extends StatelessWidget {
  final List<Map<String, dynamic>> trades; // [{type, timestamp, volumeUsd}]
  final bool embedded;

  const TradeHistoryChart({
    super.key,
    required this.trades,
    this.embedded = false,
  });

  @override
  Widget build(BuildContext context) {
    if (trades.isEmpty) {
      return const SizedBox.shrink();
    }

    // 按 30 分钟时段聚合
    final buckets = _aggregateBuckets(trades, 30);
    if (buckets.isEmpty) return const SizedBox.shrink();

    final maxVol = buckets.fold<double>(0, (m, b) =>
        max(m, max(b['buyVol'] as double, b['sellVol'] as double)));

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 标题
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Row(
            children: [
              Icon(Icons.bar_chart, size: 18, color: context.colors.textSecondary),
              const SizedBox(width: 6),
              Text(
                S.of(context).tradeHistory,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: context.colors.textPrimary,
                ),
              ),
              const Spacer(),
              // 图例
              _legend(context, S.of(context).buySimple, const Color(0xFF22C55E)),
              const SizedBox(width: 12),
              _legend(context, S.of(context).sellSimple, const Color(0xFFEF4444)),
            ],
          ),
        ),

        // 柱状图
        SizedBox(
          height: 120,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: buckets.map((b) {
              final buyVol = b['buyVol'] as double;
              final sellVol = b['sellVol'] as double;
              final buyH = maxVol > 0 ? (buyVol / maxVol * 100).clamp(2.0, 100.0) : 2.0;
              final sellH = maxVol > 0 ? (sellVol / maxVol * 100).clamp(2.0, 100.0) : 2.0;

              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 1),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      // 买入柱（绿）
                      Container(
                        height: buyH,
                        decoration: BoxDecoration(
                          color: const Color(0xFF22C55E).withValues(alpha: 0.8),
                          borderRadius: const BorderRadius.vertical(top: Radius.circular(2)),
                        ),
                      ),
                      const SizedBox(height: 1),
                      // 卖出柱（红）
                      Container(
                        height: sellH,
                        decoration: BoxDecoration(
                          color: const Color(0xFFEF4444).withValues(alpha: 0.8),
                          borderRadius: const BorderRadius.vertical(bottom: Radius.circular(2)),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
        ),

        // 时间轴标签
        const SizedBox(height: 4),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            if (buckets.isNotEmpty)
              Text(
                _formatTime(buckets.first['time'] as DateTime),
                style: TextStyle(fontSize: 10, color: context.colors.textSecondary),
              ),
            if (buckets.length > 1)
              Text(
                _formatTime(buckets.last['time'] as DateTime),
                style: TextStyle(fontSize: 10, color: context.colors.textSecondary),
              ),
          ],
        ),

        // 汇总统计
        const SizedBox(height: 12),
        _summaryRow(context, buckets),
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

  Widget _legend(BuildContext context, String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(
          color: color, borderRadius: BorderRadius.circular(2))),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(fontSize: 11, color: context.colors.textSecondary)),
      ],
    );
  }

  Widget _summaryRow(BuildContext context, List<Map<String, dynamic>> buckets) {
    double totalBuy = 0, totalSell = 0;
    int buyTx = 0, sellTx = 0;
    for (final b in buckets) {
      totalBuy += b['buyVol'] as double;
      totalSell += b['sellVol'] as double;
      buyTx += b['buyCount'] as int;
      sellTx += b['sellCount'] as int;
    }

    return Row(
      children: [
        Expanded(child: _statChip(
          context, '${S.of(context).buySimple} $buyTx ${S.of(context).txCount}',
          _fmtUsd(totalBuy), const Color(0xFF22C55E),
        )),
        const SizedBox(width: 8),
        Expanded(child: _statChip(
          context, '${S.of(context).sellSimple} $sellTx ${S.of(context).txCount}',
          _fmtUsd(totalSell), const Color(0xFFEF4444),
        )),
      ],
    );
  }

  Widget _statChip(BuildContext context, String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(fontSize: 11, color: context.colors.textSecondary)),
          Text(value, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: color)),
        ],
      ),
    );
  }

  String _fmtUsd(double v) {
    if (v >= 1e6) return '\$${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '\$${(v / 1e3).toStringAsFixed(1)}K';
    if (v > 0) return '\$${v.toStringAsFixed(0)}';
    return '\$0';
  }

  String _formatTime(DateTime t) {
    return '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
  }

  /// 按 N 分钟聚合交易
  List<Map<String, dynamic>> _aggregateBuckets(
      List<Map<String, dynamic>> trades, int minutesPerBucket) {
    if (trades.isEmpty) return [];

    // 解析时间
    final parsed = <Map<String, dynamic>>[];
    for (final t in trades) {
      DateTime? time;
      final ts = t['timestamp'] ?? t['block_timestamp'] ?? t['tx_time'];
      if (ts is DateTime) {
        time = ts;
      } else if (ts is String) {
        time = DateTime.tryParse(ts);
      } else if (ts is int) {
        time = DateTime.fromMillisecondsSinceEpoch(ts * 1000);
      }
      if (time == null) continue;

      final isBuy = (t['type'] ?? t['tx_type'] ?? t['kind'] ?? '') == 'buy';
      final vol = (t['volume_in_usd'] ?? t['volumeUsd'] ?? t['volume_usd'] ?? t['amount_usd'] ?? 0).toDouble();

      parsed.add({'time': time, 'isBuy': isBuy, 'vol': vol});
    }
    if (parsed.isEmpty) return [];

    parsed.sort((a, b) => (a['time'] as DateTime).compareTo(b['time'] as DateTime));

    final first = parsed.first['time'] as DateTime;
    final last = parsed.last['time'] as DateTime;
    final totalMin = last.difference(first).inMinutes;
    final numBuckets = max((totalMin / minutesPerBucket).ceil(), 1).clamp(1, 48);

    final buckets = List.generate(numBuckets, (i) {
      final bucketTime = first.add(Duration(minutes: i * minutesPerBucket));
      return {
        'time': bucketTime,
        'buyVol': 0.0,
        'sellVol': 0.0,
        'buyCount': 0,
        'sellCount': 0,
      };
    });

    for (final t in parsed) {
      final time = t['time'] as DateTime;
      final idx = (time.difference(first).inMinutes / minutesPerBucket).floor().clamp(0, numBuckets - 1);
      if (t['isBuy'] as bool) {
        buckets[idx]['buyVol'] = (buckets[idx]['buyVol'] as double) + (t['vol'] as double);
        buckets[idx]['buyCount'] = (buckets[idx]['buyCount'] as int) + 1;
      } else {
        buckets[idx]['sellVol'] = (buckets[idx]['sellVol'] as double) + (t['vol'] as double);
        buckets[idx]['sellCount'] = (buckets[idx]['sellCount'] as int) + 1;
      }
    }

    return buckets;
  }
}
