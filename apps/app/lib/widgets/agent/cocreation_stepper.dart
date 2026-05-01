// 共创 7 阶段进度条 — Chat Tab 顶部展示用户当前共创阶段
// 引用 docs/agent-pm/03-prd.md §2.4 共创 7 阶段
// 引用 docs/agent-pm/05-tool-catalog.md S04 signal-strategy-builder
// 引用 docs/agent-pm/17-tech-plan.md Phase 3
//
// 7 阶段:
//   idle       初始(用户还没开口)
//   clarifying Agent 澄清提问
//   draft      生成草案
//   dryRun     dry-run 预估(成本/触发频率)
//   refining   用户反馈,Agent 微调
//   confirming 用户最终确认
//   saved      策略入库
//
// 设计:横向 Stepper,完成步骤打勾,当前步骤高亮,未来步骤灰显。
//      底部一行简短描述当前阶段提示。

import 'package:flutter/material.dart';

enum CocreationStage {
  idle,
  clarifying,
  draft,
  dryRun,
  refining,
  confirming,
  saved,
}

extension CocreationStageMeta on CocreationStage {
  /// 阶段顺序索引(0-6)
  int get index => CocreationStage.values.indexOf(this);

  /// 阶段简短中文标签
  String get label {
    switch (this) {
      case CocreationStage.idle:
        return '开始';
      case CocreationStage.clarifying:
        return '澄清';
      case CocreationStage.draft:
        return '草案';
      case CocreationStage.dryRun:
        return 'Dry-run';
      case CocreationStage.refining:
        return '微调';
      case CocreationStage.confirming:
        return '确认';
      case CocreationStage.saved:
        return '保存';
    }
  }

  /// 阶段提示语(给当前 stage 用,展示在 stepper 下方)
  String get hint {
    switch (this) {
      case CocreationStage.idle:
        return '告诉 Agent 你想做什么策略,例如"做聪明钱跟单"';
      case CocreationStage.clarifying:
        return 'Agent 正在澄清细节(回答它的提问可以更准)';
      case CocreationStage.draft:
        return 'Agent 在写草案,稍候…';
      case CocreationStage.dryRun:
        return '正在估算成本与触发频率(dry-run)';
      case CocreationStage.refining:
        return '回复"再严一点 / 换条件 / 加止损"等可微调';
      case CocreationStage.confirming:
        return '看一下卡片细节,确认后即创建策略';
      case CocreationStage.saved:
        return '策略已保存,可在「我的策略」查看';
    }
  }

  /// 阶段图标
  IconData get icon {
    switch (this) {
      case CocreationStage.idle:
        return Icons.flag_outlined;
      case CocreationStage.clarifying:
        return Icons.help_outline;
      case CocreationStage.draft:
        return Icons.edit_note_outlined;
      case CocreationStage.dryRun:
        return Icons.science_outlined;
      case CocreationStage.refining:
        return Icons.tune;
      case CocreationStage.confirming:
        return Icons.check_circle_outline;
      case CocreationStage.saved:
        return Icons.task_alt;
    }
  }
}

class CocreationStepper extends StatelessWidget {
  final CocreationStage current;
  final bool collapsed;

  const CocreationStepper({
    super.key,
    required this.current,
    this.collapsed = false,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final stages = CocreationStage.values;
    final currentIdx = current.index;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      decoration: BoxDecoration(
        color: scheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: scheme.outline.withValues(alpha: 0.18)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 标题行
          Row(
            children: [
              Icon(Icons.auto_awesome, size: 16, color: scheme.primary),
              const SizedBox(width: 6),
              Text(
                '共创进度',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: scheme.onSurface.withValues(alpha: 0.7),
                ),
              ),
              const Spacer(),
              Text(
                '${currentIdx + 1} / ${stages.length}',
                style: TextStyle(
                  fontSize: 11,
                  color: scheme.onSurface.withValues(alpha: 0.5),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Stepper 横向滚动
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: List.generate(stages.length * 2 - 1, (i) {
                if (i.isOdd) return _buildConnector(scheme, i ~/ 2 < currentIdx);
                final stageIdx = i ~/ 2;
                return _buildStep(
                  scheme,
                  stages[stageIdx],
                  isDone: stageIdx < currentIdx,
                  isCurrent: stageIdx == currentIdx,
                );
              }),
            ),
          ),

          // 当前阶段提示语
          if (!collapsed) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: scheme.primary.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.info_outline, size: 14, color: scheme.primary),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      current.hint,
                      style: TextStyle(
                        fontSize: 12,
                        height: 1.4,
                        color: scheme.onSurface.withValues(alpha: 0.85),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStep(
    ColorScheme scheme,
    CocreationStage stage, {
    required bool isDone,
    required bool isCurrent,
  }) {
    final Color bg;
    final Color fg;
    final IconData iconData;
    if (isDone) {
      bg = scheme.primary;
      fg = scheme.onPrimary;
      iconData = Icons.check;
    } else if (isCurrent) {
      bg = scheme.primary.withValues(alpha: 0.18);
      fg = scheme.primary;
      iconData = stage.icon;
    } else {
      bg = scheme.surfaceContainerHighest.withValues(alpha: 0.4);
      fg = scheme.onSurface.withValues(alpha: 0.4);
      iconData = stage.icon;
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 30,
          height: 30,
          decoration: BoxDecoration(
            color: bg,
            shape: BoxShape.circle,
            border: isCurrent
                ? Border.all(color: scheme.primary, width: 1.5)
                : null,
          ),
          child: Icon(iconData, size: 16, color: fg),
        ),
        const SizedBox(height: 4),
        SizedBox(
          width: 56,
          child: Text(
            stage.label,
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 10,
              fontWeight: isCurrent ? FontWeight.w600 : FontWeight.w400,
              color: isCurrent
                  ? scheme.primary
                  : scheme.onSurface.withValues(alpha: 0.6),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildConnector(ColorScheme scheme, bool isDone) {
    return Container(
      width: 18,
      height: 2,
      margin: const EdgeInsets.only(top: 14),
      color: isDone
          ? scheme.primary
          : scheme.outline.withValues(alpha: 0.25),
    );
  }
}
