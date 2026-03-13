import 'package:flutter/material.dart';
import '../../utils/chain_utils.dart';

/// 链标签组件（玻璃风格）
class ChainBadge extends StatelessWidget {
  final String chain;
  const ChainBadge({super.key, required this.chain});

  @override
  Widget build(BuildContext context) {
    final color = ChainUtils.getColor(chain);
    final label = ChainUtils.getLabel(chain);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.15), width: 0.5),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 9,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.3,
        ),
      ),
    );
  }
}
