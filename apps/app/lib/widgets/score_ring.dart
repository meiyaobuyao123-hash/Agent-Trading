import 'dart:math';
import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

/// 圆形分数环 — 渐变 stroke + count-up 入场动画
class ScoreRing extends StatefulWidget {
  final double score;
  final double size;
  final double strokeWidth;
  final bool animate;

  const ScoreRing({
    super.key,
    required this.score,
    this.size = 52,
    this.strokeWidth = 4,
    this.animate = true,
  });

  @override
  State<ScoreRing> createState() => _ScoreRingState();
}

class _ScoreRingState extends State<ScoreRing>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _progressAnim;
  late Animation<double> _countAnim;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    _progressAnim = CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic);
    _countAnim = Tween<double>(begin: 0, end: widget.score).animate(_progressAnim);
    if (widget.animate) {
      _controller.forward();
    } else {
      _controller.value = 1.0;
    }
  }

  @override
  void didUpdateWidget(ScoreRing old) {
    super.didUpdateWidget(old);
    if (old.score != widget.score) {
      _countAnim = Tween<double>(begin: 0, end: widget.score).animate(_progressAnim);
      _controller.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Color get _color {
    if (widget.score >= 75) return context.colors.success;
    if (widget.score >= 55) return context.colors.warning;
    return context.colors.textTertiary;
  }

  Color get _colorLight {
    if (widget.score >= 75) return context.colors.success.withValues(alpha: 0.35);
    if (widget.score >= 55) return context.colors.warning.withValues(alpha: 0.35);
    return context.colors.textTertiary.withValues(alpha: 0.35);
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          return Stack(
            alignment: Alignment.center,
            children: [
              CustomPaint(
                size: Size(widget.size, widget.size),
                painter: _GradientRingPainter(
                  progress: (widget.score / 100) * _progressAnim.value,
                  color: _color,
                  colorLight: _colorLight,
                  trackColor: context.colors.divider.withValues(alpha: 0.3),
                  strokeWidth: widget.strokeWidth,
                ),
              ),
              Text(
                _countAnim.value.toInt().toString(),
                style: TextStyle(
                  color: _color,
                  fontSize: widget.size * 0.28,
                  fontWeight: FontWeight.w800,
                  height: 1,
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _GradientRingPainter extends CustomPainter {
  final double progress;
  final Color color;
  final Color colorLight;
  final Color trackColor;
  final double strokeWidth;

  const _GradientRingPainter({
    required this.progress,
    required this.color,
    required this.colorLight,
    required this.trackColor,
    required this.strokeWidth,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width - strokeWidth) / 2;
    final rect = Rect.fromCircle(center: center, radius: radius);

    // 背景圆 — 更轻的颜色
    canvas.drawCircle(
      center, radius,
      Paint()
        ..color = trackColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth,
    );

    if (progress <= 0) return;

    // 渐变进度弧
    final sweepAngle = 2 * pi * progress;
    final gradient = SweepGradient(
      startAngle: -pi / 2,
      endAngle: -pi / 2 + sweepAngle,
      colors: [colorLight, color],
      tileMode: TileMode.clamp,
    ).createShader(rect);

    canvas.drawArc(
      rect,
      -pi / 2,
      sweepAngle,
      false,
      Paint()
        ..shader = gradient
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(_GradientRingPainter old) =>
      old.progress != progress || old.color != color;
}
