import 'package:flutter/material.dart';
import '../models/daily_pick.dart';
import '../theme/app_colors.dart';
import 'score_ring.dart';

class PickCard extends StatelessWidget {
  final DailyPick pick;
  final VoidCallback? onTap;

  const PickCard({super.key, required this.pick, this.onTap});

  @override
  Widget build(BuildContext context) {
    final isStrong = pick.recommendation == 'strong';
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isStrong
                ? AppColors.strong.withValues(alpha: 0.3)
                : AppColors.divider,
            width: isStrong ? 1.5 : 0.5,
          ),
          boxShadow: AppColors.cardShadow,
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── 头部：排名 + 名称 + 分数环 ───────
              Row(
                children: [
                  _RankBadge(rank: pick.rank),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          pick.symbol.toUpperCase(),
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                            letterSpacing: -0.3,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          pick.name,
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 12,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                  ScoreRing(score: pick.score),
                ],
              ),

              const SizedBox(height: 14),

              // ── 指标行 ────────────────────────────
              Row(
                children: [
                  _StatChip(
                    label: 'BC进度',
                    value: '${pick.bcProgress.toStringAsFixed(1)}%',
                    color: AppColors.primary,
                  ),
                  const SizedBox(width: 8),
                  _StatChip(
                    label: '市值',
                    value: '${pick.marketCapSol.toStringAsFixed(0)} SOL',
                    color: AppColors.textSecondary,
                  ),
                  const SizedBox(width: 8),
                  _RecommendChip(rec: pick.recommendation),
                ],
              ),

              // ── 有结果时显示结果 ──────────────────
              if (pick.hasOutcome) ...[
                const SizedBox(height: 10),
                _OutcomeRow(pick: pick),
              ],

              // ── Social 图标 ───────────────────────
              if (pick.twitter != null || pick.telegram != null || pick.website != null) ...[
                const SizedBox(height: 10),
                _SocialRow(pick: pick),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

// ─── 排名 badge ─────────────────────────────────────
class _RankBadge extends StatelessWidget {
  final int rank;
  const _RankBadge({required this.rank});

  Color get _bg {
    if (rank == 1) return const Color(0xFFFFD700);
    if (rank == 2) return const Color(0xFFC0C0C0);
    if (rank == 3) return const Color(0xFFCD7F32);
    return AppColors.primaryDim;
  }

  Color get _fg {
    if (rank <= 3) return const Color(0xFF1A1A1A);
    return AppColors.primary;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        color: _bg,
        borderRadius: BorderRadius.circular(10),
      ),
      alignment: Alignment.center,
      child: Text(
        '#$rank',
        style: TextStyle(
          color: _fg,
          fontSize: 12,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

// ─── 指标小片 ────────────────────────────────────────
class _StatChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _StatChip({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.surfaceAlt,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label,
            style: const TextStyle(color: AppColors.textTertiary, fontSize: 10)),
          const SizedBox(height: 1),
          Text(value,
            style: TextStyle(color: color, fontSize: 12,
              fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

// ─── 推荐等级 ────────────────────────────────────────
class _RecommendChip extends StatelessWidget {
  final String rec;
  const _RecommendChip({required this.rec});

  @override
  Widget build(BuildContext context) {
    final isStrong = rec == 'strong';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: isStrong ? AppColors.strongLight : AppColors.normalLight,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isStrong ? Icons.rocket_launch_rounded : Icons.trending_up_rounded,
            size: 12,
            color: isStrong ? AppColors.strong : AppColors.normal,
          ),
          const SizedBox(width: 4),
          Text(
            isStrong ? '强烈推荐' : '关注',
            style: TextStyle(
              color: isStrong ? AppColors.strong : AppColors.normal,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

// ─── 结果行 ──────────────────────────────────────────
class _OutcomeRow extends StatelessWidget {
  final DailyPick pick;
  const _OutcomeRow({required this.pick});

  @override
  Widget build(BuildContext context) {
    final is2x = pick.label2x == true;
    final isGrad = pick.didGraduate == true;
    final color = (is2x || isGrad) ? AppColors.success : AppColors.danger;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: (is2x || isGrad) ? AppColors.successLight : AppColors.dangerLight,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            pick.outcomeLabel,
            style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600),
          ),
          if (pick.peakMultiplier != null) ...[
            const SizedBox(width: 8),
            Text(
              '峰值 ${pick.peakMultiplier!.toStringAsFixed(1)}x',
              style: TextStyle(color: color.withValues(alpha: 0.7), fontSize: 11),
            ),
          ],
        ],
      ),
    );
  }
}

// ─── Social 图标行 ────────────────────────────────────
class _SocialRow extends StatelessWidget {
  final DailyPick pick;
  const _SocialRow({required this.pick});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        if (pick.twitter != null)
          _SocialDot(label: 'TW', color: const Color(0xFF1DA1F2)),
        if (pick.telegram != null)
          _SocialDot(label: 'TG', color: const Color(0xFF2AABEE)),
        if (pick.website != null)
          _SocialDot(label: 'WEB', color: AppColors.textSecondary),
      ],
    );
  }
}

class _SocialDot extends StatelessWidget {
  final String label;
  final Color color;
  const _SocialDot({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(right: 6),
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(label,
        style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w600)),
    );
  }
}
