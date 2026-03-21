import 'package:flutter/material.dart';
import '../../models/btc_eth.dart';

/// 风险仪表盘 — 恐慌指数 + 资金费率 + RSI + 复合评分
class RiskDashboard extends StatelessWidget {
  final BtcEthAssetSummary data;
  final String asset;

  const RiskDashboard({super.key, required this.data, required this.asset});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$asset Risk Dashboard',
              style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.7), fontSize: 12)),
          const SizedBox(height: 10),
          Row(
            children: [
              _gaugeItem('Fear/Greed', data.fearGreed?.toDouble() ?? 50,
                  _fgiColor(data.fearGreed ?? 50)),
              _gaugeItem('RSI', data.rsi ?? 50, _rsiColor(data.rsi ?? 50)),
              _gaugeItem('Funding',
                  ((data.fundingRate ?? 0) * 10000).clamp(-100, 100),
                  _fundingColor(data.fundingRate ?? 0),
                  suffix: 'bps'),
            ],
          ),
          const SizedBox(height: 10),
          // 复合评分条
          Row(
            children: data.scores.entries.map((e) {
              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2),
                  child: Column(
                    children: [
                      Text(e.key[0].toUpperCase() + e.key.substring(1),
                          style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.5),
                              fontSize: 9)),
                      const SizedBox(height: 3),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(3),
                        child: LinearProgressIndicator(
                          value: e.value / 100,
                          minHeight: 6,
                          backgroundColor: Colors.white.withValues(alpha: 0.1),
                          valueColor: AlwaysStoppedAnimation(
                              _scoreColor(e.value)),
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text('${e.value}',
                          style: TextStyle(
                              color: _scoreColor(e.value), fontSize: 10)),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _gaugeItem(String label, double value, Color color, {String? suffix}) {
    return Expanded(
      child: Column(
        children: [
          Text(label,
              style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.5), fontSize: 10)),
          const SizedBox(height: 4),
          Text(
            suffix != null
                ? '${value.toStringAsFixed(1)} $suffix'
                : value.toStringAsFixed(0),
            style: TextStyle(
                color: color, fontSize: 18, fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }

  Color _fgiColor(int val) {
    if (val <= 20) return const Color(0xFFEF4444);
    if (val <= 40) return const Color(0xFFF97316);
    if (val <= 60) return const Color(0xFFFBBF24);
    if (val <= 80) return const Color(0xFF22C55E);
    return const Color(0xFF10B981);
  }

  Color _rsiColor(double val) {
    if (val <= 30) return const Color(0xFF22C55E); // 超卖=机会
    if (val >= 70) return const Color(0xFFEF4444); // 超买=风险
    return Colors.white70;
  }

  Color _fundingColor(double val) {
    if (val > 0.01) return const Color(0xFFEF4444); // 多头拥挤
    if (val < -0.005) return const Color(0xFF22C55E); // 空头拥挤=做多机会
    return Colors.white70;
  }

  Color _scoreColor(int val) {
    if (val >= 70) return const Color(0xFF22C55E);
    if (val >= 50) return const Color(0xFFFBBF24);
    if (val >= 30) return const Color(0xFFF97316);
    return const Color(0xFFEF4444);
  }
}
