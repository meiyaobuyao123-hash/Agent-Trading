import 'package:flutter/material.dart';

/// 7 阶段周期状态条
class CycleStatusBar extends StatelessWidget {
  final String currentPhase;
  final double confidence;

  static const phases = [
    'accumulation', 'recovery', 'breakout',
    'bull_run', 'euphoria', 'distribution', 'bear',
  ];

  static const phaseLabels = {
    'accumulation': 'Accum',
    'recovery': 'Recovery',
    'breakout': 'Breakout',
    'bull_run': 'Bull Run',
    'euphoria': 'Euphoria',
    'distribution': 'Distrib',
    'bear': 'Bear',
  };

  static const phaseColors = {
    'accumulation': Color(0xFF6B7280),
    'recovery': Color(0xFF10B981),
    'breakout': Color(0xFF3B82F6),
    'bull_run': Color(0xFF22C55E),
    'euphoria': Color(0xFFF59E0B),
    'distribution': Color(0xFFF97316),
    'bear': Color(0xFFEF4444),
  };

  const CycleStatusBar({
    super.key,
    required this.currentPhase,
    required this.confidence,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'Market Cycle',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.7),
                  fontSize: 12,
                ),
              ),
              const Spacer(),
              Text(
                'Confidence: ${confidence.toStringAsFixed(0)}%',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.5),
                  fontSize: 11,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: phases.map((phase) {
              final isActive = phase == currentPhase;
              final color = phaseColors[phase] ?? Colors.grey;
              final label = phaseLabels[phase] ?? phase;
              return Expanded(
                child: Container(
                  height: 28,
                  margin: const EdgeInsets.symmetric(horizontal: 1),
                  decoration: BoxDecoration(
                    color: isActive ? color : color.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                    border: isActive
                        ? Border.all(color: Colors.white, width: 1.5)
                        : null,
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    label,
                    style: TextStyle(
                      color: isActive ? Colors.white : Colors.white.withValues(alpha: 0.4),
                      fontSize: 9,
                      fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}
