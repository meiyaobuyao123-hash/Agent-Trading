import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import '../models/daily_pick.dart';
import '../theme/app_colors.dart';

class PickCard extends StatelessWidget {
  final DailyPick pick;
  final VoidCallback? onTap;

  const PickCard({super.key, required this.pick, this.onTap});

  @override
  Widget build(BuildContext context) {
    final isStrong = pick.recommendation == 'strong';

    return CupertinoButton(
      padding: EdgeInsets.zero,
      onPressed: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            // ── 代币头像（网络图片 + 排名角标） ──────
            _TokenAvatar(pick: pick),
            const SizedBox(width: 12),

            // ── 名称 + 指标 ──────────────────
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          pick.symbol.toUpperCase(),
                          style: const TextStyle(
                            color: AppColors.textPrimary, fontSize: 16,
                            fontWeight: FontWeight.w600, letterSpacing: -0.3,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (isStrong) ...[
                        const SizedBox(width: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                          decoration: BoxDecoration(
                            color: AppColors.strong.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text('强推',
                              style: TextStyle(color: AppColors.strong, fontSize: 10, fontWeight: FontWeight.w700)),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 2),
                  Row(
                    children: [
                      Text(
                        'BC ${pick.bcProgress.toStringAsFixed(1)}%',
                        style: const TextStyle(
                          color: AppColors.primary, fontSize: 13, fontWeight: FontWeight.w500,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        '${pick.marketCapSol.toStringAsFixed(0)} SOL',
                        style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
                      ),
                      if (pick.hasOutcome) ...[
                        const SizedBox(width: 8),
                        _OutcomeBadge(pick: pick),
                      ],
                    ],
                  ),
                ],
              ),
            ),

            // ── 右侧：分数 + 箭头 ──────────────
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _ScoreBadge(score: pick.score),
                const SizedBox(width: 4),
                const Icon(CupertinoIcons.chevron_right, size: 14, color: AppColors.textTertiary),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// ─── 代币头像（网络图片 or 排名首字母） ──────────────
class _TokenAvatar extends StatelessWidget {
  final DailyPick pick;
  const _TokenAvatar({required this.pick});

  Color get _rankColor {
    if (pick.rank == 1) return const Color(0xFFFFD700);
    if (pick.rank == 2) return const Color(0xFFC0C0C0);
    if (pick.rank == 3) return const Color(0xFFCD7F32);
    return AppColors.primary;
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 44, height: 44,
      child: Stack(
        children: [
          // 主头像
          if (pick.imageUri != null && pick.imageUri!.isNotEmpty)
            Container(
              width: 44, height: 44,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: AppColors.primary.withValues(alpha: 0.15), width: 1.5),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: Image.network(
                  pick.imageUri!,
                  width: 41, height: 41, fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => _letterAvatar(),
                ),
              ),
            )
          else
            _letterAvatar(),

          // 排名角标
          if (pick.rank <= 10)
            Positioned(
              right: 0, bottom: 0,
              child: Container(
                width: 16, height: 16,
                decoration: BoxDecoration(
                  color: _rankColor,
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.surface, width: 1.5),
                ),
                alignment: Alignment.center,
                child: Text('${pick.rank}',
                    style: TextStyle(
                      color: pick.rank <= 3 ? Colors.white : Colors.white,
                      fontSize: 9, fontWeight: FontWeight.w800,
                    )),
              ),
            ),
        ],
      ),
    );
  }

  Widget _letterAvatar() {
    return Container(
      width: 44, height: 44,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [AppColors.primary.withValues(alpha: 0.15), AppColors.primary.withValues(alpha: 0.05)],
        ),
        borderRadius: BorderRadius.circular(22),
      ),
      alignment: Alignment.center,
      child: Text(
        pick.symbol.isNotEmpty ? pick.symbol[0].toUpperCase() : '?',
        style: TextStyle(color: AppColors.primary, fontSize: 18, fontWeight: FontWeight.w700),
      ),
    );
  }
}

// ─── 分数徽章 ────────────────────────────────────────
class _ScoreBadge extends StatelessWidget {
  final double score;
  const _ScoreBadge({required this.score});

  Color get _color {
    if (score >= 75) return AppColors.strong;
    if (score >= 55) return AppColors.normal;
    return AppColors.textSecondary;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: _color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        score.toStringAsFixed(0),
        style: TextStyle(color: _color, fontSize: 15, fontWeight: FontWeight.w700),
      ),
    );
  }
}

// ─── 结果小标签 ──────────────────────────────────────
class _OutcomeBadge extends StatelessWidget {
  final DailyPick pick;
  const _OutcomeBadge({required this.pick});

  @override
  Widget build(BuildContext context) {
    final good = pick.label2x == true || pick.didGraduate == true;
    final color = good ? AppColors.success : AppColors.danger;

    return Text(
      pick.outcomeLabel,
      style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600),
    );
  }
}
