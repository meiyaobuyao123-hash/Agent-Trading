import 'dart:ui';
import 'package:flutter/material.dart';
import 'app_colors.dart';

/// 毛玻璃卡片 — Glassmorphism 核心组件
///
/// [useBlur] 控制是否启用 BackdropFilter：
///   - 列表内卡片设 false（性能优先）
///   - AppBar / 弹窗 / 浮层设 true
class GlassCard extends StatelessWidget {
  final Widget child;
  final double borderRadius;
  final double blurSigma;
  final bool useBlur;
  final EdgeInsets? margin;
  final EdgeInsets? padding;
  final Color? overrideColor;
  final Color? overrideBorder;
  final VoidCallback? onTap;

  const GlassCard({
    super.key,
    required this.child,
    this.borderRadius = 16,
    this.blurSigma = 20,
    this.useBlur = false,
    this.margin,
    this.padding,
    this.overrideColor,
    this.overrideBorder,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final bgColor = overrideColor ?? colors.cardGlass;
    final borderColor = overrideBorder ?? colors.glassBorder;

    Widget card = Container(
      margin: margin,
      decoration: BoxDecoration(
        color: useBlur ? bgColor : bgColor,
        borderRadius: BorderRadius.circular(borderRadius),
        border: Border.all(color: borderColor, width: 0.5),
        boxShadow: colors.cardShadow,
      ),
      child: Padding(
        padding: padding ?? const EdgeInsets.all(16),
        child: child,
      ),
    );

    if (useBlur) {
      card = ClipRRect(
        borderRadius: BorderRadius.circular(borderRadius),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: blurSigma, sigmaY: blurSigma),
          child: card,
        ),
      );
    }

    if (onTap != null) {
      return GestureDetector(onTap: onTap, child: card);
    }

    return card;
  }
}

/// 带渐变光晕的毛玻璃卡片
class GlowGlassCard extends StatelessWidget {
  final Widget child;
  final Color glowColor;
  final double borderRadius;
  final EdgeInsets? margin;
  final EdgeInsets? padding;

  const GlowGlassCard({
    super.key,
    required this.child,
    required this.glowColor,
    this.borderRadius = 16,
    this.margin,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Container(
      margin: margin,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(borderRadius),
        boxShadow: [
          BoxShadow(
            color: glowColor.withValues(alpha: 0.15),
            blurRadius: 24,
            spreadRadius: -4,
          ),
        ],
      ),
      child: Container(
        decoration: BoxDecoration(
          color: colors.cardGlass,
          borderRadius: BorderRadius.circular(borderRadius),
          border: Border.all(
            color: glowColor.withValues(alpha: 0.2),
            width: 0.5,
          ),
        ),
        child: Padding(
          padding: padding ?? const EdgeInsets.all(16),
          child: child,
        ),
      ),
    );
  }
}

/// 简化版玻璃容器 — 用于内嵌小区域
class GlassSurface extends StatelessWidget {
  final Widget child;
  final double borderRadius;
  final EdgeInsets? padding;

  const GlassSurface({
    super.key,
    required this.child,
    this.borderRadius = 12,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Container(
      padding: padding ?? const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: colors.surface,
        borderRadius: BorderRadius.circular(borderRadius),
        border: Border.all(color: colors.glassBorder, width: 0.5),
      ),
      child: child,
    );
  }
}
