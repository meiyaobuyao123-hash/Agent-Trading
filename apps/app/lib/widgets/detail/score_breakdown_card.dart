import 'package:flutter/material.dart';
import '../../models/token_detail.dart';
import '../../theme/app_colors.dart';
import '../score_ring.dart';

/// AI 评分卡片 — ScoreRing + 维度进度条
class ScoreBreakdownCard extends StatelessWidget {
  final TokenDetail token;
  const ScoreBreakdownCard({super.key, required this.token});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(color: Color(0x0A000000), blurRadius: 10, offset: Offset(0, 2)),
        ],
        border: Border.all(
          color: _scoreColor(token.score).withValues(alpha: 0.12),
          width: 1,
        ),
      ),
      child: Column(
        children: [
          // ScoreRing 居中
          ScoreRing(score: token.score, size: 80, strokeWidth: 5),
          const SizedBox(height: 10),
          Text(
            _recommendation(token.recommendation),
            style: TextStyle(
              fontSize: 15, fontWeight: FontWeight.w600,
              color: _scoreColor(token.score),
            ),
          ),
          const SizedBox(height: 18),

          // M/Q/P 维度
          if (token.scoreM != null) ...[
            _ScoreBar(label: '动量 M', value: token.scoreM!, max: 50),
            const SizedBox(height: 10),
            _ScoreBar(label: '品质 Q', value: token.scoreQ ?? 0, max: 30),
            const SizedBox(height: 10),
            _ScoreBar(label: '潜力 P', value: token.scoreP ?? 0, max: 20),
          ] else if (token.scoreDetail != null && token.scoreDetail!.isNotEmpty) ...[
            ...token.scoreDetail!.entries.map((e) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _ScoreBar(
                label: _zhLabel(e.key),
                value: (e.value as num?)?.toDouble() ?? 0,
                max: 15,
              ),
            )),
          ],
        ],
      ),
    );
  }

  Color _scoreColor(double s) {
    if (s >= 72) return AppColors.strong;
    if (s >= 50) return AppColors.normal;
    return AppColors.textSecondary;
  }

  String _recommendation(String r) => switch (r) {
    'strong' => 'AI 建议: 强推',
    'normal' => 'AI 建议: 值得关注',
    _ => 'AI 建议: 观望',
  };

  String _zhLabel(String key) => switch (key) {
    'buy_sell' => '买卖比',
    'smart_money' => '聪明钱',
    'inflow_accel' => '流入加速',
    'creator_history' => '创建者',
    'buyer_diversity' => '买家分散',
    'social_score' => '社交',
    'progress_speed' => '进度速度',
    'whale_bonus' => '大单加成',
    _ => key,
  };
}

class _ScoreBar extends StatelessWidget {
  final String label;
  final double value;
  final double max;
  const _ScoreBar({required this.label, required this.value, required this.max});

  @override
  Widget build(BuildContext context) {
    final ratio = (value / max).clamp(0.0, 1.0);
    final color = ratio > 0.7 ? AppColors.strong
        : ratio > 0.4 ? AppColors.normal
        : AppColors.textTertiary;

    return Row(
      children: [
        SizedBox(width: 60,
          child: Text(label, style: const TextStyle(fontSize: 13, color: AppColors.textSecondary))),
        Expanded(
          child: Container(
            height: 10,
            decoration: BoxDecoration(
              color: AppColors.bg,
              borderRadius: BorderRadius.circular(5),
            ),
            child: FractionallySizedBox(
              widthFactor: ratio,
              alignment: Alignment.centerLeft,
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [color.withValues(alpha: 0.4), color],
                  ),
                  borderRadius: BorderRadius.circular(5),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(width: 52,
          child: Text('${value.toStringAsFixed(1)}/${max.toInt()}',
              textAlign: TextAlign.right,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
                  color: AppColors.textSecondary))),
      ],
    );
  }
}
