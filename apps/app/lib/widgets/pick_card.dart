import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import '../models/daily_pick.dart';
import '../theme/app_colors.dart';
import 'common/token_avatar.dart';
import 'common/rank_medal.dart';

/// Glassmorphism 风格内盘推荐卡片
class PickCard extends StatelessWidget {
  final DailyPick pick;
  final VoidCallback? onTap;

  const PickCard({super.key, required this.pick, this.onTap});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final isStrong = pick.recommendation == 'strong';

    return CupertinoButton(
      padding: EdgeInsets.zero,
      onPressed: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
        child: Row(
          children: [
            // ── 排名 ────────────────────
            SizedBox(
              width: 24,
              child: pick.rank <= 3
                  ? RankMedal(rank: pick.rank)
                  : Text(
                      '${pick.rank}',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: pick.rank <= 10 ? c.textSecondary : c.textTertiary,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
            ),
            const SizedBox(width: 8),

            // ── 头像 ────────────────────
            TokenAvatar(imageUrl: pick.imageUri, symbol: pick.symbol, chain: 'solana', size: 38),
            const SizedBox(width: 10),

            // ── 中间列 ──────────────────
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    children: [
                      Text(
                        pick.symbol.toUpperCase(),
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: c.textPrimary,
                          letterSpacing: -0.3,
                        ),
                      ),
                      if (isStrong) ...[
                        const SizedBox(width: 5),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                          decoration: BoxDecoration(
                            gradient: c.successGradient,
                            borderRadius: BorderRadius.circular(4),
                            boxShadow: [
                              BoxShadow(
                                color: c.success.withValues(alpha: 0.3),
                                blurRadius: 4,
                              ),
                            ],
                          ),
                          child: const Text(
                            '强推',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 5),

                  // 行2: BC% · MC · 结果
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                        decoration: BoxDecoration(
                          color: c.primary.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: c.primary.withValues(alpha: 0.15), width: 0.5),
                        ),
                        child: Text(
                          'BC ${pick.bcProgress.toStringAsFixed(1)}%',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: c.primary,
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        '${pick.marketCapSol.toStringAsFixed(0)} SOL',
                        style: TextStyle(fontSize: 11, color: c.textSecondary),
                      ),
                      if (pick.hasOutcome) ...[
                        const SizedBox(width: 6),
                        _OutcomePill(pick: pick),
                      ],
                    ],
                  ),
                ],
              ),
            ),

            // ── 右侧：评分框 ─────────────
            _ScoreBox(score: pick.score),
            const SizedBox(width: 4),
            Icon(CupertinoIcons.chevron_right, size: 12, color: c.textTertiary),
          ],
        ),
      ),
    );
  }
}

// ─── 评分框（渐变填充）──────────────────────────
class _ScoreBox extends StatelessWidget {
  final double score;
  const _ScoreBox({required this.score});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final gradient = score >= 75
        ? c.successGradient
        : score >= 55
            ? c.primaryGradient
            : LinearGradient(colors: [c.textSecondary, c.textTertiary]);

    return Container(
      constraints: const BoxConstraints(minWidth: 38),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: BorderRadius.circular(6),
        boxShadow: [
          BoxShadow(
            color: (score >= 75 ? c.success : c.primary).withValues(alpha: 0.2),
            blurRadius: 4,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      alignment: Alignment.center,
      child: Text(
        score.toStringAsFixed(0),
        style: const TextStyle(
          color: Colors.white,
          fontSize: 13,
          fontWeight: FontWeight.w800,
          fontFeatures: [FontFeature.tabularFigures()],
        ),
      ),
    );
  }
}

// ─── 结果胶囊 ──────────────────────────────────
class _OutcomePill extends StatelessWidget {
  final DailyPick pick;
  const _OutcomePill({required this.pick});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final good = pick.label2x == true || pick.didGraduate == true;
    final color = good ? c.success : c.danger;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.15), width: 0.5),
      ),
      child: Text(
        pick.outcomeLabel,
        style: TextStyle(
          color: color,
          fontSize: 10,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
