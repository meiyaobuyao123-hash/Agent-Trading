import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';
import '../../theme/app_colors.dart';

/// 详情页加载骨架屏
class ShimmerSkeleton extends StatelessWidget {
  const ShimmerSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor: context.colors.cardGlass,
      highlightColor: context.colors.cardGlass,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 头部骨架
          _card(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                _box(44, 44, radius: 22),
                const SizedBox(width: 12),
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  _box(100, 16),
                  const SizedBox(height: 6),
                  _box(60, 12),
                ]),
              ]),
              const SizedBox(height: 16),
              _box(180, 32),
              const SizedBox(height: 10),
              Row(children: [
                _box(60, 24, radius: 6),
                const SizedBox(width: 8),
                _box(60, 24, radius: 6),
                const SizedBox(width: 8),
                _box(60, 24, radius: 6),
              ]),
            ],
          )),
          const SizedBox(height: 12),

          // K线图骨架
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 16),
            height: 320,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
            ),
          ),
          const SizedBox(height: 12),

          // 指标行骨架
          _card(child: Row(
            children: List.generate(5, (i) => Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: Column(children: [
                  _box(40, 10),
                  const SizedBox(height: 6),
                  _box(56, 14),
                ]),
              ),
            )),
          )),
          const SizedBox(height: 12),

          // 评分骨架
          _card(child: Column(children: [
            _box(80, 80, radius: 40),
            const SizedBox(height: 12),
            _box(120, 12),
            const SizedBox(height: 10),
            _box(double.infinity, 10),
            const SizedBox(height: 8),
            _box(double.infinity, 10),
          ])),
        ],
      ),
    );
  }

  Widget _card({required Widget child}) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: child,
    );
  }

  Widget _box(double w, double h, {double radius = 4}) {
    return Container(
      width: w == double.infinity ? null : w,
      height: h,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(radius),
      ),
    );
  }
}
