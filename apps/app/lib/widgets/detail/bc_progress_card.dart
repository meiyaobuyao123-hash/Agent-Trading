import 'package:flutter/material.dart';
import '../../models/token_detail.dart';
import '../../theme/app_colors.dart';

/// pump.fun 专属 — Bonding Curve 进度卡片
class BcProgressCard extends StatelessWidget {
  final TokenDetail token;
  const BcProgressCard({super.key, required this.token});

  @override
  Widget build(BuildContext context) {
    final bc = token.bcProgress ?? 0;
    final pct = (bc * 100).clamp(0.0, 100.0);
    final remaining = (100 - pct).clamp(0.0, 100.0);

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.primary.withValues(alpha: 0.08),
            const Color(0xFF7C3AED).withValues(alpha: 0.06),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: AppColors.primary.withValues(alpha: 0.15),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 标题行
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.rocket_launch_rounded,
                    size: 16, color: AppColors.primary),
              ),
              const SizedBox(width: 10),
              const Text('Bonding Curve',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary)),
              const Spacer(),
              Text('${pct.toStringAsFixed(1)}%',
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800,
                      color: AppColors.primary)),
            ],
          ),
          const SizedBox(height: 14),

          // 进度条（带里程碑标记）
          SizedBox(
            height: 14,
            child: Stack(
              children: [
                // 背景
                Container(
                  height: 14,
                  decoration: BoxDecoration(
                    color: AppColors.surfaceAlt,
                    borderRadius: BorderRadius.circular(7),
                  ),
                ),
                // 进度
                FractionallySizedBox(
                  widthFactor: bc.clamp(0.0, 1.0),
                  child: Container(
                    height: 14,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF2563EB), Color(0xFF7C3AED)],
                      ),
                      borderRadius: BorderRadius.circular(7),
                    ),
                  ),
                ),
                // 里程碑标记 25%, 50%, 75%
                for (final m in [0.25, 0.5, 0.75])
                  Positioned(
                    left: 0,
                    right: 0,
                    child: FractionallySizedBox(
                      widthFactor: m,
                      alignment: Alignment.centerLeft,
                      child: Align(
                        alignment: Alignment.centerRight,
                        child: Container(
                          width: 2,
                          height: 14,
                          color: Colors.white.withValues(alpha: 0.3),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 8),

          // 距离毕业提示
          if (pct < 100)
            Text(
              '距离毕业还差 ${remaining.toStringAsFixed(1)}%',
              style: TextStyle(
                fontSize: 13,
                color: AppColors.textSecondary,
              ),
            ),
          const SizedBox(height: 10),

          // 标签
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              if (token.didGraduate != null)
                _Tag(
                  label: token.didGraduate! ? '已毕业' : '未毕业',
                  color: token.didGraduate! ? AppColors.success : AppColors.textSecondary,
                  icon: token.didGraduate! ? Icons.check_circle : Icons.pending,
                ),
              if (token.label2x == true)
                const _Tag(label: '2x', color: AppColors.normal, icon: Icons.trending_up),
              if (token.label10x == true)
                const _Tag(label: '10x', color: AppColors.strong, icon: Icons.rocket),
            ],
          ),
        ],
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;
  const _Tag({required this.label, required this.color, this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 13, color: color),
            const SizedBox(width: 4),
          ],
          Text(label,
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color)),
        ],
      ),
    );
  }
}
