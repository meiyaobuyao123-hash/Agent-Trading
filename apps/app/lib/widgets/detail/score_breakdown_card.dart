import 'package:flutter/material.dart';
import '../../l10n/app_localizations.dart';
import '../../models/token_detail.dart';
import '../../theme/app_colors.dart';
import '../score_ring.dart';

/// AI 评分卡片 — ScoreRing + 维度进度条（带入场动画）
class ScoreBreakdownCard extends StatefulWidget {
  final TokenDetail token;
  const ScoreBreakdownCard({super.key, required this.token});

  @override
  State<ScoreBreakdownCard> createState() => _ScoreBreakdownCardState();
}

class _ScoreBreakdownCardState extends State<ScoreBreakdownCard>
    with SingleTickerProviderStateMixin {
  late AnimationController _barController;

  @override
  void initState() {
    super.initState();
    _barController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..forward();
  }

  @override
  void dispose() {
    _barController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final token = widget.token;
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(16),
        boxShadow: context.colors.cardShadow,
        border: Border.all(
          color: _scoreColor(token.score).withValues(alpha: 0.10),
          width: 1,
        ),
      ),
      child: Column(
        children: [
          // ScoreRing 居中
          ScoreRing(score: token.score, size: 86, strokeWidth: 6),
          const SizedBox(height: 12),
          // 推荐标签 — premium 胶囊
          _RecommendationLabel(
            recommendation: token.recommendation,
            color: _scoreColor(token.score),
          ),
          const SizedBox(height: 20),

          // M/Q/P 维度
          if (token.scoreM != null) ...[
            _AnimatedScoreBar(label: S.of(context).momentumM, value: token.scoreM!, max: 50, animation: _barController),
            const SizedBox(height: 12),
            _AnimatedScoreBar(label: S.of(context).qualityQ, value: token.scoreQ ?? 0, max: 30, animation: _barController),
            const SizedBox(height: 12),
            _AnimatedScoreBar(label: S.of(context).potentialP, value: token.scoreP ?? 0, max: 20, animation: _barController),
          ] else if (token.scoreDetail != null && token.scoreDetail!.isNotEmpty) ...[
            ...token.scoreDetail!.entries.map((e) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _AnimatedScoreBar(
                label: _zhLabel(e.key),
                value: (e.value as num?)?.toDouble() ?? 0,
                max: 15,
                animation: _barController,
              ),
            )),
          ],
        ],
      ),
    );
  }

  Color _scoreColor(double s) {
    if (s >= 72) return context.colors.success;
    if (s >= 50) return context.colors.warning;
    return context.colors.textSecondary;
  }

  String _zhLabel(String key) => switch (key) {
    'buy_sell' => S.of(context).buySellRatio,
    'smart_money' => S.of(context).smartMoneyLabel,
    'inflow_accel' => S.of(context).inflowAccel,
    'creator_history' => S.of(context).creatorLabel,
    'buyer_diversity' => S.of(context).buyerDiversity,
    'social_score' => S.of(context).socialLabel,
    'progress_speed' => S.of(context).progressSpeed,
    'whale_bonus' => S.of(context).whaleBonus,
    _ => key,
  };
}

/// 推荐标签 — 半透明胶囊
class _RecommendationLabel extends StatelessWidget {
  final String recommendation;
  final Color color;
  const _RecommendationLabel({required this.recommendation, required this.color});

  @override
  Widget build(BuildContext context) {
    final (text, icon) = switch (recommendation) {
      'strong' => (S.of(context).aiStrongPush, Icons.bolt_rounded),
      'normal' => (S.of(context).aiWatch, Icons.visibility_rounded),
      _ => (S.of(context).aiObserve, Icons.remove_red_eye_outlined),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.20)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(text, style: TextStyle(
            fontSize: 13, fontWeight: FontWeight.w700, color: color,
          )),
        ],
      ),
    );
  }
}

/// 进度条 — 带入场动画 + 圆角端点 + 渐变
class _AnimatedScoreBar extends StatelessWidget {
  final String label;
  final double value;
  final double max;
  final Animation<double> animation;
  const _AnimatedScoreBar({
    required this.label,
    required this.value,
    required this.max,
    required this.animation,
  });

  @override
  Widget build(BuildContext context) {
    final ratio = (value / max).clamp(0.0, 1.0);
    final color = ratio > 0.7 ? context.colors.success
        : ratio > 0.4 ? context.colors.warning
        : context.colors.textTertiary;

    return AnimatedBuilder(
      animation: animation,
      builder: (context, _) {
        final animatedRatio = ratio * Curves.easeOutCubic.transform(animation.value);
        return Row(
          children: [
            SizedBox(width: 62,
              child: Text(label, style: TextStyle(
                fontSize: 13, color: context.colors.textSecondary, fontWeight: FontWeight.w500))),
            Expanded(
              child: Container(
                height: 8,
                decoration: BoxDecoration(
                  color: context.colors.bg,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: FractionallySizedBox(
                  widthFactor: animatedRatio,
                  alignment: Alignment.centerLeft,
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [color.withValues(alpha: 0.45), color],
                      ),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 10),
            SizedBox(width: 54,
              child: Text('${(value * Curves.easeOutCubic.transform(animation.value)).toStringAsFixed(1)}/${max.toInt()}',
                  textAlign: TextAlign.right,
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700,
                      color: context.colors.textSecondary,
                      fontFeatures: [FontFeature.tabularFigures()]))),
          ],
        );
      },
    );
  }
}
