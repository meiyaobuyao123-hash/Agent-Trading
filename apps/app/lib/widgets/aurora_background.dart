import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/gradients.dart';

/// 极光背景 — 所有页面共用
///
/// 用法：作为 Stack 第一层，子内容叠在上方
/// ```dart
/// Stack(children: [
///   const AuroraBackground(),
///   // your content
/// ]);
/// ```
class AuroraBackground extends StatelessWidget {
  final Widget? child;

  const AuroraBackground({super.key, this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppGradients.screenBg(context),
      child: Stack(
        children: [
          // 极光光斑（仅 Dark 模式）
          ...AppGradients.auroraSpots(context),
          // 子内容
          if (child != null) child!,
        ],
      ),
    );
  }
}

/// 页面级脚手架 — 自带极光背景
/// 替代 Scaffold(backgroundColor: ...)
class AuroraScaffold extends StatelessWidget {
  final Widget body;
  final PreferredSizeWidget? appBar;
  final Widget? bottomNavigationBar;
  final bool extendBody;
  final bool extendBodyBehindAppBar;

  const AuroraScaffold({
    super.key,
    required this.body,
    this.appBar,
    this.bottomNavigationBar,
    this.extendBody = false,
    this.extendBodyBehindAppBar = false,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Scaffold(
      backgroundColor: c.bg,
      extendBody: extendBody,
      extendBodyBehindAppBar: extendBodyBehindAppBar,
      appBar: appBar,
      body: Stack(
        children: [
          // 渐变底色
          Positioned.fill(
            child: Container(decoration: AppGradients.screenBg(context)),
          ),
          // 极光光斑
          ...AppGradients.auroraSpots(context),
          // 页面内容
          Positioned.fill(child: body),
        ],
      ),
      bottomNavigationBar: bottomNavigationBar,
    );
  }
}
