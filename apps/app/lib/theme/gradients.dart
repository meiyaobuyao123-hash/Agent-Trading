import 'package:flutter/material.dart';
import 'app_colors.dart';

/// 渐变工具集 — 极光 / 背景 / 光晕 / 渐变文字
class AppGradients {
  AppGradients._();

  // ── 屏幕渐变背景 ──────────────────────────
  static BoxDecoration screenBg(BuildContext context) {
    final c = context.colors;
    return BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [c.bg, c.bgSecondary],
      ),
    );
  }

  // ── 极光光斑（屏幕背景装饰）──────────────
  static List<Widget> auroraSpots(BuildContext context) {
    final c = context.colors;
    final isDark = context.isDark;
    if (!isDark) return []; // Light 模式无极光

    return [
      // 左上蓝光
      Positioned(
        top: -80,
        left: -60,
        child: Container(
          width: 260,
          height: 260,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(
              colors: [
                c.primary.withValues(alpha: 0.08),
                c.primary.withValues(alpha: 0.0),
              ],
            ),
          ),
        ),
      ),
      // 右上紫光
      Positioned(
        top: 100,
        right: -80,
        child: Container(
          width: 220,
          height: 220,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(
              colors: [
                const Color(0xFF8B5CF6).withValues(alpha: 0.06),
                const Color(0xFF8B5CF6).withValues(alpha: 0.0),
              ],
            ),
          ),
        ),
      ),
      // 底部青光
      Positioned(
        bottom: -40,
        left: 40,
        child: Container(
          width: 200,
          height: 200,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(
              colors: [
                const Color(0xFF06B6D4).withValues(alpha: 0.05),
                const Color(0xFF06B6D4).withValues(alpha: 0.0),
              ],
            ),
          ),
        ),
      ),
    ];
  }

  // ── 渐变文字 ──────────────────────────────
  static Widget gradientText({
    required String text,
    required TextStyle style,
    List<Color>? colors,
  }) {
    return ShaderMask(
      shaderCallback: (bounds) => LinearGradient(
        colors: colors ?? const [Color(0xFF3B82F6), Color(0xFF8B5CF6)],
      ).createShader(bounds),
      child: Text(text, style: style.copyWith(color: Colors.white)),
    );
  }

  // ── 语义渐变胶囊（涨/跌）──────────────────
  static BoxDecoration changeCapsule(
    BuildContext context, {
    required bool isPositive,
    double borderRadius = 8,
  }) {
    final c = context.colors;
    return BoxDecoration(
      gradient: isPositive ? c.successGradient : c.dangerGradient,
      borderRadius: BorderRadius.circular(borderRadius),
    );
  }

  // ── 光晕装饰 ──────────────────────────────
  static BoxDecoration glowDecoration(Color color, {double borderRadius = 12}) {
    return BoxDecoration(
      borderRadius: BorderRadius.circular(borderRadius),
      boxShadow: [
        BoxShadow(
          color: color.withValues(alpha: 0.2),
          blurRadius: 16,
          spreadRadius: -2,
        ),
      ],
    );
  }

  // ── 排名渐变 ──────────────────────────────
  static LinearGradient? rankGradient(int rank) {
    switch (rank) {
      case 1:
        return const LinearGradient(
          colors: [Color(0xFFFFD700), Color(0xFFFF8C00)],
        );
      case 2:
        return const LinearGradient(
          colors: [Color(0xFFC0C0C0), Color(0xFF9CA3AF)],
        );
      case 3:
        return const LinearGradient(
          colors: [Color(0xFFCD7F32), Color(0xFFB8860B)],
        );
      default:
        return null;
    }
  }

  // ── 评分环渐变 ──────────────────────────────
  static List<Color> scoreRingColors(double score) {
    if (score >= 80) return [const Color(0xFF10B981), const Color(0xFF34D399)];
    if (score >= 60) return [const Color(0xFF3B82F6), const Color(0xFF60A5FA)];
    if (score >= 40) return [const Color(0xFFF59E0B), const Color(0xFFFBBF24)];
    return [const Color(0xFFEF4444), const Color(0xFFF87171)];
  }
}
