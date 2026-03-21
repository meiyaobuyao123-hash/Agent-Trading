import 'package:flutter/material.dart';
import '../../models/btc_eth.dart';

/// BTC/ETH 交易信号卡片
class BtcEthSignalCard extends StatelessWidget {
  final BtcEthSignal signal;

  const BtcEthSignalCard({super.key, required this.signal});

  @override
  Widget build(BuildContext context) {
    final isLong = signal.isLong;
    final color = isLong ? const Color(0xFF22C55E) : const Color(0xFFEF4444);
    final icon = isLong ? Icons.trending_up : Icons.trending_down;
    final label = isLong ? 'LONG' : 'SHORT';

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 头部：方向 + 资产 + 置信度
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(icon, color: Colors.white, size: 14),
                    const SizedBox(width: 4),
                    Text(label,
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.bold)),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Text(signal.asset,
                  style: const TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold)),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '${signal.confidence}%',
                  style: TextStyle(
                    color: signal.confidence >= 70 ? const Color(0xFF22C55E) : Colors.white70,
                    fontSize: 12,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // 价格行
          Row(
            children: [
              _priceItem('Entry', signal.entryPrice, Colors.white),
              _priceItem('Stop', signal.stopLoss, const Color(0xFFEF4444)),
              _priceItem('Target', signal.targetPrice, const Color(0xFF22C55E)),
              _priceItem('R:R', signal.riskReward, const Color(0xFF3B82F6), isRatio: true),
            ],
          ),

          // 理由
          if (signal.reasoning != null && signal.reasoning!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              signal.reasoning!,
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.6),
                fontSize: 11,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],

          // 状态 + 时间
          const SizedBox(height: 6),
          Row(
            children: [
              if (!signal.isActive)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: signal.status == 'hit_target'
                        ? const Color(0xFF22C55E).withValues(alpha: 0.2)
                        : const Color(0xFFEF4444).withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    signal.status == 'hit_target' ? 'TARGET HIT' : 'STOPPED',
                    style: TextStyle(
                      color: signal.status == 'hit_target'
                          ? const Color(0xFF22C55E)
                          : const Color(0xFFEF4444),
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              const Spacer(),
              Text(
                _timeAgo(signal.createdAt),
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.4),
                  fontSize: 10,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _priceItem(String label, double value, Color color, {bool isRatio = false}) {
    return Expanded(
      child: Column(
        children: [
          Text(label,
              style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.5), fontSize: 10)),
          const SizedBox(height: 2),
          Text(
            isRatio ? '${value.toStringAsFixed(1)}:1' : '\$${_fmtPrice(value)}',
            style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }

  String _fmtPrice(double p) {
    if (p >= 10000) return p.toStringAsFixed(0);
    if (p >= 100) return p.toStringAsFixed(1);
    return p.toStringAsFixed(2);
  }

  String _timeAgo(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}
