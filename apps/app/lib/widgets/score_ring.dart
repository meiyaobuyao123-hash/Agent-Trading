import 'dart:math';
import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

/// 圆形分数环，内部显示数字
class ScoreRing extends StatelessWidget {
  final double score;
  final double size;
  final double strokeWidth;

  const ScoreRing({
    super.key,
    required this.score,
    this.size = 52,
    this.strokeWidth = 4,
  });

  Color get _color {
    if (score >= 75) return AppColors.strong;
    if (score >= 55) return AppColors.normal;
    return AppColors.textTertiary;
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          CustomPaint(
            size: Size(size, size),
            painter: _RingPainter(
              progress: score / 100,
              color: _color,
              strokeWidth: strokeWidth,
            ),
          ),
          Text(
            score.toInt().toString(),
            style: TextStyle(
              color: _color,
              fontSize: size * 0.28,
              fontWeight: FontWeight.w800,
              height: 1,
            ),
          ),
        ],
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  final double progress;
  final Color color;
  final double strokeWidth;

  const _RingPainter({
    required this.progress,
    required this.color,
    required this.strokeWidth,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width - strokeWidth) / 2;

    // 背景圆
    canvas.drawCircle(
      center, radius,
      Paint()
        ..color = AppColors.divider
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth,
    );

    // 进度弧
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -pi / 2,
      2 * pi * progress,
      false,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(_RingPainter old) =>
      old.progress != progress || old.color != color;
}
