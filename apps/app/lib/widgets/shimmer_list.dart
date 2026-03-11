import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

/// 列表 Shimmer 骨架屏 — 主题感知
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
    final c = context.colors;
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: c.cardGlass,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: c.glassBorder, width: 0.5),
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
                    color: c.divider,
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
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        children: [
          _shimmerBox(c, 46, 46, isCircle: true),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _shimmerBox(c, 80, 14),
                const SizedBox(height: 6),
                _shimmerBox(c, 110, 11),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              _shimmerBox(c, 72, 14),
              const SizedBox(height: 6),
              _shimmerBox(c, 56, 22, radius: 8),
            ],
          ),
        ],
      ),
    );
  }

  Widget _shimmerBox(AppColorScheme c, double width, double height,
      {bool isCircle = false, double radius = 6}) {
    return ShaderMask(
      shaderCallback: (bounds) {
        return LinearGradient(
          begin: Alignment(-1.0 + 2.0 * progress, 0),
          end: Alignment(-0.5 + 2.0 * progress, 0),
          colors: [
            c.shimmerBase,
            c.shimmerHighlight,
            c.shimmerBase,
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
