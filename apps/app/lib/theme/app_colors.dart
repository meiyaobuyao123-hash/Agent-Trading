import 'package:flutter/material.dart';

/// iOS 原生风格配色
/// 参考：Apple Stocks / Health / 优质 iOS 金融应用
class AppColors {
  AppColors._();

  // ── 背景 ──────────────────────────────
  static const bg           = Color(0xFFF2F2F7);   // iOS systemGroupedBackground
  static const surface      = Color(0xFFFFFFFF);
  static const surfaceAlt   = Color(0xFFE5E5EA);   // iOS systemGray5

  // ── 主色 ──────────────────────────────
  static const primary      = Color(0xFF007AFF);   // iOS systemBlue
  static const primaryLight = Color(0xFFE8F2FF);
  static const primaryDim   = Color(0xFFD6E8FF);

  // ── 信号 ──────────────────────────────
  static const strong       = Color(0xFF34C759);   // iOS systemGreen
  static const strongLight  = Color(0xFFE8FAF0);
  static const normal       = Color(0xFFFF9500);   // iOS systemOrange
  static const normalLight  = Color(0xFFFFF4E6);

  // ── 语义 ──────────────────────────────
  static const success      = Color(0xFF34C759);
  static const successLight = Color(0xFFE8FAF0);
  static const danger       = Color(0xFFFF3B30);   // iOS systemRed
  static const dangerLight  = Color(0xFFFEECEB);
  static const warning      = Color(0xFFFF9500);
  static const warningLight = Color(0xFFFFF4E6);

  // ── 文字 ──────────────────────────────
  static const textPrimary   = Color(0xFF000000);
  static const textSecondary = Color(0xFF8E8E93);   // iOS secondaryLabel
  static const textTertiary  = Color(0xFFC7C7CC);

  // ── 线条 ──────────────────────────────
  static const divider       = Color(0xFFC6C6C8);
  static const border        = Color(0xFFD1D1D6);

  // ── 图标 ──────────────────────────────
  static const iconInactive  = Color(0xFF8E8E93);

  // ── K线图深色主题 ────────────────────
  static const chartBg        = Color(0xFF1A1D26);
  static const chartSurface   = Color(0xFF222531);
  static const chartGrid      = Color(0xFF2A2D38);
  static const chartCrosshair = Color(0xFF8E8E93);
  static const chartBullish   = Color(0xFF00C853);
  static const chartBearish   = Color(0xFFFF1744);

  // ── 阴影（iOS 极轻）──────────────────
  static const shadow        = Color(0x0C000000);
  static const List<BoxShadow> cardShadow = [
    BoxShadow(color: Color(0x08000000), blurRadius: 8, offset: Offset(0, 2)),
  ];
  static const List<BoxShadow> cardShadowMd = [
    BoxShadow(color: Color(0x10000000), blurRadius: 16, offset: Offset(0, 4)),
  ];
}
