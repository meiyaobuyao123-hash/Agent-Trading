import 'package:flutter/material.dart';

// ══════════════════════════════════════════════════════════════
//  双主题色彩系统 — Glassmorphism 2026
// ══════════════════════════════════════════════════════════════

/// 主题感知配色方案
class AppColorScheme {
  // ── 背景 ──
  final Color bg;
  final Color bgSecondary;
  final Color surface;
  final Color surfaceAlt;

  // ── 毛玻璃 ──
  final Color cardGlass;
  final Color glassBorder;
  final Color glassHighlight;

  // ── 主色 ──
  final Color primary;
  final Color primaryGlow;
  final Color primaryLight;

  // ── 语义 ──
  final Color success;
  final Color successLight;
  final Color danger;
  final Color dangerLight;
  final Color warning;
  final Color warningLight;

  // ── 文字 ──
  final Color textPrimary;
  final Color textSecondary;
  final Color textTertiary;
  final Color textInverse;

  // ── 线条 ──
  final Color divider;
  final Color border;

  // ── 图标 ──
  final Color iconPrimary;
  final Color iconInactive;

  // ── Shimmer ──
  final Color shimmerBase;
  final Color shimmerHighlight;

  // ── K线图 ──
  final Color chartBg;
  final Color chartSurface;
  final Color chartGrid;
  final Color chartCrosshair;
  final Color chartBullish;
  final Color chartBearish;

  // ── 强调 ──
  final Color accentGold;
  final Color accentGoldDim;

  // ── 阴影 ──
  final List<BoxShadow> cardShadow;
  final List<BoxShadow> cardShadowMd;
  final List<BoxShadow> cardShadowLg;

  // ── 渐变 ──
  final LinearGradient primaryGradient;
  final LinearGradient successGradient;
  final LinearGradient dangerGradient;

  const AppColorScheme({
    required this.bg,
    required this.bgSecondary,
    required this.surface,
    required this.surfaceAlt,
    required this.cardGlass,
    required this.glassBorder,
    required this.glassHighlight,
    required this.primary,
    required this.primaryGlow,
    required this.primaryLight,
    required this.success,
    required this.successLight,
    required this.danger,
    required this.dangerLight,
    required this.warning,
    required this.warningLight,
    required this.textPrimary,
    required this.textSecondary,
    required this.textTertiary,
    required this.textInverse,
    required this.divider,
    required this.border,
    required this.iconPrimary,
    required this.iconInactive,
    required this.shimmerBase,
    required this.shimmerHighlight,
    required this.chartBg,
    required this.chartSurface,
    required this.chartGrid,
    required this.chartCrosshair,
    required this.chartBullish,
    required this.chartBearish,
    required this.accentGold,
    required this.accentGoldDim,
    required this.cardShadow,
    required this.cardShadowMd,
    required this.cardShadowLg,
    required this.primaryGradient,
    required this.successGradient,
    required this.dangerGradient,
  });

  // ═══════════════════════════════════════════════
  //  Dark 配色 — 默认主题
  // ═══════════════════════════════════════════════
  static const dark = AppColorScheme(
    bg: Color(0xFF0A0E1A),
    bgSecondary: Color(0xFF111827),
    surface: Color(0x0DFFFFFF),       // 5%
    surfaceAlt: Color(0xFF1A1F2E),

    cardGlass: Color(0x0FFFFFFF),     // 6%
    glassBorder: Color(0x1AFFFFFF),   // 10%
    glassHighlight: Color(0x08FFFFFF),// 3%

    primary: Color(0xFF3B82F6),
    primaryGlow: Color(0x263B82F6),   // 15%
    primaryLight: Color(0x1A3B82F6),  // 10%

    success: Color(0xFF10B981),
    successLight: Color(0x1A10B981),
    danger: Color(0xFFEF4444),
    dangerLight: Color(0x1AEF4444),
    warning: Color(0xFFF59E0B),
    warningLight: Color(0x1AF59E0B),

    textPrimary: Color(0xF2FFFFFF),   // 95%
    textSecondary: Color(0x99FFFFFF), // 60%
    textTertiary: Color(0x59FFFFFF),  // 35%
    textInverse: Color(0xFF0A0E1A),

    divider: Color(0x1AFFFFFF),       // 10%
    border: Color(0x14FFFFFF),        // 8%

    iconPrimary: Color(0xF2FFFFFF),
    iconInactive: Color(0x66FFFFFF),  // 40%

    shimmerBase: Color(0xFF1A1F2E),
    shimmerHighlight: Color(0xFF2A2F3E),

    chartBg: Color(0xFF0A0E1A),
    chartSurface: Color(0xFF111827),
    chartGrid: Color(0xFF1E2433),
    chartCrosshair: Color(0x99FFFFFF),
    chartBullish: Color(0xFF10B981),
    chartBearish: Color(0xFFEF4444),

    accentGold: Color(0xFFFFB81C),
    accentGoldDim: Color(0x26FFB81C),

    cardShadow: [
      BoxShadow(color: Color(0x33000000), blurRadius: 12, offset: Offset(0, 4)),
    ],
    cardShadowMd: [
      BoxShadow(color: Color(0x4D000000), blurRadius: 24, offset: Offset(0, 8)),
    ],
    cardShadowLg: [
      BoxShadow(color: Color(0x66000000), blurRadius: 40, offset: Offset(0, 16)),
    ],

    primaryGradient: LinearGradient(
      colors: [Color(0xFF3B82F6), Color(0xFF8B5CF6)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
    successGradient: LinearGradient(
      colors: [Color(0xFF10B981), Color(0xFF34D399)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
    dangerGradient: LinearGradient(
      colors: [Color(0xFFEF4444), Color(0xFFF87171)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
  );

  // ═══════════════════════════════════════════════
  //  Light 配色
  // ═══════════════════════════════════════════════
  static const light = AppColorScheme(
    // 纯净白底 — 参考 Coinbase/Robinhood 高端风格
    bg: Color(0xFFFAFAFC),            // 微灰白，比纯白更舒适
    bgSecondary: Color(0xFFF3F4F6),   // 区块背景
    surface: Color(0xFFFFFFFF),        // 卡片纯白
    surfaceAlt: Color(0xFFF9FAFB),    // 交替行

    cardGlass: Color(0xFFFFFFFF),      // 白卡片，不要灰蓝调
    glassBorder: Color(0x0F000000),    // 6% 极淡边框
    glassHighlight: Color(0x08000000), // 微妙高光

    primary: Color(0xFF1D4ED8),        // 深蓝，更有质感
    primaryGlow: Color(0x1A1D4ED8),
    primaryLight: Color(0xFFEFF6FF),

    success: Color(0xFF16A34A),        // 鲜绿
    successLight: Color(0xFFF0FDF4),
    danger: Color(0xFFDC2626),         // 红
    dangerLight: Color(0xFFFEF2F2),
    warning: Color(0xFFEA580C),        // 橙
    warningLight: Color(0xFFFFF7ED),

    textPrimary: Color(0xFF111827),    // 近黑，高对比
    textSecondary: Color(0xFF6B7280),  // 中灰，清晰可读
    textTertiary: Color(0xFF9CA3AF),   // 浅灰，辅助信息
    textInverse: Color(0xFFFFFFFF),

    divider: Color(0xFFE5E7EB),        // 淡灰分割线
    border: Color(0xFFE5E7EB),         // 统一边框色

    iconPrimary: Color(0xFF111827),
    iconInactive: Color(0xFF9CA3AF),

    shimmerBase: Color(0xFFF3F4F6),
    shimmerHighlight: Color(0xFFFFFFFF),

    chartBg: Color(0xFFFFFFFF),
    chartSurface: Color(0xFFFAFAFC),
    chartGrid: Color(0xFFF3F4F6),
    chartCrosshair: Color(0xFF6B7280),
    chartBullish: Color(0xFF16A34A),
    chartBearish: Color(0xFFDC2626),

    accentGold: Color(0xFFD97706),
    accentGoldDim: Color(0x1AD97706),

    cardShadow: [
      BoxShadow(color: Color(0x08000000), blurRadius: 8, offset: Offset(0, 1)),
      BoxShadow(color: Color(0x05000000), blurRadius: 2, offset: Offset(0, 0)),
    ],
    cardShadowMd: [
      BoxShadow(color: Color(0x0D000000), blurRadius: 16, offset: Offset(0, 4)),
      BoxShadow(color: Color(0x05000000), blurRadius: 4, offset: Offset(0, 1)),
    ],
    cardShadowLg: [
      BoxShadow(color: Color(0x12000000), blurRadius: 24, offset: Offset(0, 8)),
      BoxShadow(color: Color(0x08000000), blurRadius: 6, offset: Offset(0, 2)),
    ],

    primaryGradient: LinearGradient(
      colors: [Color(0xFF1D4ED8), Color(0xFF6366F1)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
    successGradient: LinearGradient(
      colors: [Color(0xFF16A34A), Color(0xFF4ADE80)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
    dangerGradient: LinearGradient(
      colors: [Color(0xFFDC2626), Color(0xFFF87171)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
  );
}

/// BuildContext 扩展 — 便捷访问当前主题配色
extension AppColorsX on BuildContext {
  AppColorScheme get colors =>
      Theme.of(this).brightness == Brightness.dark
          ? AppColorScheme.dark
          : AppColorScheme.light;

  bool get isDark => Theme.of(this).brightness == Brightness.dark;
}

// ══════════════════════════════════════════════════════════════
//  向后兼容 — 旧代码 AppColors.xxx 仍可用
//  新代码请统一用 context.colors.xxx
// ══════════════════════════════════════════════════════════════
class AppColors {
  AppColors._();

  // ── 背景 ──
  static const bg           = Color(0xFFF2F2F7);
  static const surface      = Color(0xFFFFFFFF);
  static const surfaceAlt   = Color(0xFFE5E5EA);

  // ── 主色 ──
  static const primary      = Color(0xFF007AFF);
  static const primaryLight = Color(0xFFE8F2FF);
  static const primaryDim   = Color(0xFFD6E8FF);

  // ── 信号 ──
  static const strong       = Color(0xFF34C759);
  static const strongLight  = Color(0xFFE8FAF0);
  static const normal       = Color(0xFFFF9500);
  static const normalLight  = Color(0xFFFFF4E6);

  // ── 语义 ──
  static const success      = Color(0xFF34C759);
  static const successLight = Color(0xFFE8FAF0);
  static const danger       = Color(0xFFFF3B30);
  static const dangerLight  = Color(0xFFFEECEB);
  static const warning      = Color(0xFFFF9500);
  static const warningLight = Color(0xFFFFF4E6);

  // ── 文字 ──
  static const textPrimary   = Color(0xFF000000);
  static const textSecondary = Color(0xFF8E8E93);
  static const textTertiary  = Color(0xFFC7C7CC);

  // ── 线条 ──
  static const divider       = Color(0xFFC6C6C8);
  static const border        = Color(0xFFD1D1D6);

  // ── 图标 ──
  static const iconInactive  = Color(0xFF8E8E93);

  // ── K线图深色主题 ──
  static const chartBg        = Color(0xFF1A1D26);
  static const chartSurface   = Color(0xFF222531);
  static const chartGrid      = Color(0xFF2A2D38);
  static const chartCrosshair = Color(0xFF8E8E93);
  static const chartBullish   = Color(0xFF00C853);
  static const chartBearish   = Color(0xFFFF1744);

  // ── 强调 ──
  static const accentGold    = Color(0xFFFFB81C);
  static const accentGoldDim = Color(0x26FFB81C);

  // ── 阴影 ──
  static const shadow        = Color(0x0C000000);
  static const List<BoxShadow> cardShadow = [
    BoxShadow(color: Color(0x0A000000), blurRadius: 10, offset: Offset(0, 2)),
  ];
  static const List<BoxShadow> cardShadowMd = [
    BoxShadow(color: Color(0x12000000), blurRadius: 20, offset: Offset(0, 4)),
  ];
  static const List<BoxShadow> cardShadowLg = [
    BoxShadow(color: Color(0x18000000), blurRadius: 30, offset: Offset(0, 8)),
  ];
}
