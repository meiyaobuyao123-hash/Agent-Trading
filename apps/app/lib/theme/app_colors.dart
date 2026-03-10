import 'package:flutter/material.dart';

/// 白底极简科技风格
/// 参考：Linear / Stripe / Notion 设计系统
class AppColors {
  AppColors._();

  // ── 背景层级 ──────────────────────────────
  static const bg           = Color(0xFFF5F7FA);   // 页面底色（冷灰白）
  static const surface      = Color(0xFFFFFFFF);   // 卡片（纯白）
  static const surfaceAlt   = Color(0xFFF0F2F5);   // 次级背景

  // ── 主色 ──────────────────────────────────
  static const primary      = Color(0xFF2563EB);   // 科技蓝
  static const primaryLight = Color(0xFFEFF4FF);   // 蓝浅底
  static const primaryDim   = Color(0xFFDBEAFE);   // badge 底色

  // ── 信号 ──────────────────────────────────
  static const strong       = Color(0xFF059669);   // 强烈推荐（翠绿）
  static const strongLight  = Color(0xFFECFDF5);
  static const normal       = Color(0xFFD97706);   // 普通关注（琥珀）
  static const normalLight  = Color(0xFFFEF3C7);

  // ── 语义 ──────────────────────────────────
  static const success      = Color(0xFF10B981);
  static const successLight = Color(0xFFD1FAE5);
  static const danger       = Color(0xFFEF4444);
  static const dangerLight  = Color(0xFFFEE2E2);
  static const warning      = Color(0xFFF59E0B);
  static const warningLight = Color(0xFFFEF3C7);

  // ── 文字 ──────────────────────────────────
  static const textPrimary   = Color(0xFF0F172A);   // 主文字
  static const textSecondary = Color(0xFF64748B);   // 副文字
  static const textTertiary  = Color(0xFF94A3B8);   // Hint

  // ── 线条 ──────────────────────────────────
  static const divider       = Color(0xFFE2E8F0);
  static const border        = Color(0xFFCBD5E1);

  // ── 图标 ──────────────────────────────────
  static const iconInactive  = Color(0xFFADB5BD);

  // ── 阴影 ──────────────────────────────────
  static const shadow        = Color(0x0A0F172A);
  static const List<BoxShadow> cardShadow = [
    BoxShadow(color: Color(0x0A0F172A), blurRadius: 12, offset: Offset(0, 2)),
    BoxShadow(color: Color(0x050F172A), blurRadius: 4,  offset: Offset(0, 0)),
  ];
  static const List<BoxShadow> cardShadowMd = [
    BoxShadow(color: Color(0x120F172A), blurRadius: 24, offset: Offset(0, 4)),
    BoxShadow(color: Color(0x080F172A), blurRadius: 8,  offset: Offset(0, 1)),
  ];
}
