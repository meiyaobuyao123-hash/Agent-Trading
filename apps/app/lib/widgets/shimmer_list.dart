import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

/// 列表 Shimmer 骨架屏 — 加载时显示闪烁占位
class ShimmerList extends StatefulWidget {
  final int itemCount;
  const ShimmerList({super.key, this.itemCount = 8});

  @override
  State<ShimmerList> createState() => _ShimmerListState();
}

class _ShimmerListState extends State<ShimmerList>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        boxShadow: AppColors.cardShadow,
      ),
      child: Column(
        children: List.generate(widget.itemCount, (i) {
          return Column(
            children: [
              AnimatedBuilder(
                animation: _controller,
                builder: (context, _) {
                  return _ShimmerItem(progress: _controller.value);
                },
              ),
              if (i < widget.itemCount - 1)
                Padding(
                  padding: const EdgeInsets.only(left: 72),
                  child: Divider(
                    height: 0.5,
                    thickness: 0.5,
                    color: AppColors.divider.withValues(alpha: 0.15),
                  ),
                ),
            ],
          );
        }),
      ),
    );
  }
}

class _ShimmerItem extends StatelessWidget {
  final double progress;
  const _ShimmerItem({required this.progress});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        children: [
          // 头像
          _shimmerBox(46, 46, isCircle: true),
          const SizedBox(width: 12),
          // 名称 + 信息
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _shimmerBox(80, 14),
                const SizedBox(height: 6),
                _shimmerBox(110, 11),
              ],
            ),
          ),
          // 价格 + 涨跌
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              _shimmerBox(72, 14),
              const SizedBox(height: 6),
              _shimmerBox(56, 22, radius: 8),
            ],
          ),
        ],
      ),
    );
  }

  Widget _shimmerBox(double width, double height, {bool isCircle = false, double radius = 6}) {
    return ShaderMask(
      shaderCallback: (bounds) {
        return LinearGradient(
          begin: Alignment(-1.0 + 2.0 * progress, 0),
          end: Alignment(-0.5 + 2.0 * progress, 0),
          colors: const [
            Color(0xFFE8E8ED),
            Color(0xFFF5F5F8),
            Color(0xFFE8E8ED),
          ],
        ).createShader(bounds);
      },
      blendMode: BlendMode.srcIn,
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: isCircle ? null : BorderRadius.circular(radius),
          shape: isCircle ? BoxShape.circle : BoxShape.rectangle,
        ),
      ),
    );
  }
}
