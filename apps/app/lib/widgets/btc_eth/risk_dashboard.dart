import 'package:flutter/material.dart';
import '../../models/btc_eth.dart';

/// 市场状态仪表盘 — 通俗易懂版
class RiskDashboard extends StatelessWidget {
  final BtcEthAssetSummary data;
  final String asset;

  const RiskDashboard({super.key, required this.data, required this.asset});

  @override
  Widget build(BuildContext context) {
    final fgi = data.fearGreed ?? 50;
    final rsi = data.rsi ?? 50;
    final funding = data.fundingRate ?? 0;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 标题
          Row(
            children: [
              const Icon(Icons.dashboard, color: Colors.white54, size: 14),
              const SizedBox(width: 6),
              Text('$asset Market Status',
                  style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.7), fontSize: 13, fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 12),

          // 三个指标卡片
          Row(
            children: [
              _indicatorCard(
                icon: Icons.mood,
                title: 'Market Mood',
                value: fgi.toString(),
                label: _fgiLabel(fgi),
                color: _fgiColor(fgi),
                progress: fgi / 100,
              ),
              const SizedBox(width: 8),
              _indicatorCard(
                icon: Icons.speed,
                title: 'Momentum',
                value: rsi.toStringAsFixed(0),
                label: _rsiLabel(rsi),
                color: _rsiColor(rsi),
                progress: rsi / 100,
              ),
              const SizedBox(width: 8),
              _indicatorCard(
                icon: Icons.account_balance,
                title: 'Leverage',
                value: '${(funding * 100).toStringAsFixed(3)}%',
                label: _fundingLabel(funding),
                color: _fundingColor(funding),
                progress: (funding * 5000 + 50).clamp(0, 100) / 100,
              ),
            ],
          ),
          const SizedBox(height: 10),

          // 综合评分
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.03),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: data.scores.entries.map((e) {
                final label = _scoreLabel(e.key);
                final color = _scoreColor(e.value);
                return Expanded(
                  child: Column(
                    children: [
                      Text(label,
                          style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.5),
                              fontSize: 10)),
                      const SizedBox(height: 4),
                      SizedBox(
                        width: 36,
                        height: 36,
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            CircularProgressIndicator(
                              value: e.value / 100,
                              strokeWidth: 3,
                              backgroundColor: Colors.white.withValues(alpha: 0.08),
                              valueColor: AlwaysStoppedAnimation(color),
                            ),
                            Text('${e.value}',
                                style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold)),
                          ],
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _indicatorCard({
    required IconData icon,
    required String title,
    required String value,
    required String label,
    required Color color,
    required double progress,
  }) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withValues(alpha: 0.15)),
        ),
        child: Column(
          children: [
            Icon(icon, color: color, size: 16),
            const SizedBox(height: 4),
            Text(value,
                style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 2),
            Text(label,
                style: TextStyle(color: color.withValues(alpha: 0.8), fontSize: 10, fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            ClipRRect(
              borderRadius: BorderRadius.circular(2),
              child: LinearProgressIndicator(
                value: progress.clamp(0, 1),
                minHeight: 3,
                backgroundColor: Colors.white.withValues(alpha: 0.1),
                valueColor: AlwaysStoppedAnimation(color),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _fgiLabel(int val) {
    if (val <= 10) return 'Extreme Fear';
    if (val <= 25) return 'Fear';
    if (val <= 45) return 'Cautious';
    if (val <= 55) return 'Neutral';
    if (val <= 75) return 'Greedy';
    if (val <= 90) return 'Very Greedy';
    return 'Extreme Greed';
  }

  String _rsiLabel(double val) {
    if (val <= 20) return 'Very Oversold';
    if (val <= 30) return 'Oversold';
    if (val <= 45) return 'Weak';
    if (val <= 55) return 'Neutral';
    if (val <= 70) return 'Strong';
    if (val <= 80) return 'Overbought';
    return 'Very Overbought';
  }

  String _fundingLabel(double val) {
    if (val > 0.02) return 'Longs Crowded';
    if (val > 0.005) return 'Bullish Bias';
    if (val > -0.005) return 'Balanced';
    if (val > -0.02) return 'Bearish Bias';
    return 'Shorts Crowded';
  }

  String _scoreLabel(String key) {
    const labels = {
      'momentum': 'Trend',
      'sentiment': 'Mood',
      'onchain': 'Chain',
      'macro': 'Macro',
      'risk': 'Safety',
    };
    return labels[key] ?? key;
  }

  Color _fgiColor(int val) {
    if (val <= 20) return const Color(0xFFEF4444);
    if (val <= 40) return const Color(0xFFF97316);
    if (val <= 60) return const Color(0xFFFBBF24);
    if (val <= 80) return const Color(0xFF22C55E);
    return const Color(0xFF10B981);
  }

  Color _rsiColor(double val) {
    if (val <= 30) return const Color(0xFF22C55E);
    if (val >= 70) return const Color(0xFFEF4444);
    return const Color(0xFF64748B);
  }

  Color _fundingColor(double val) {
    if (val > 0.01) return const Color(0xFFEF4444);
    if (val < -0.005) return const Color(0xFF22C55E);
    return const Color(0xFF64748B);
  }

  Color _scoreColor(int val) {
    if (val >= 70) return const Color(0xFF22C55E);
    if (val >= 50) return const Color(0xFFFBBF24);
    if (val >= 30) return const Color(0xFFF97316);
    return const Color(0xFFEF4444);
  }
}
