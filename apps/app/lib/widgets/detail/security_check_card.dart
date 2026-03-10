import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import '../../models/goplus_report.dart';
import '../../theme/app_colors.dart';

/// 安全检测 — 横向滚动标签 + 醒目安全标识
class SecurityCheckCard extends StatelessWidget {
  final GoPlusReport? report;
  final bool loading;
  final bool embedded;

  const SecurityCheckCard({super.key, this.report, this.loading = false, this.embedded = false});

  @override
  Widget build(BuildContext context) {
    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Text('安全检测',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary)),
            const Spacer(),
            if (report != null)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: report!.overallRisk
                      ? AppColors.danger.withValues(alpha: 0.1)
                      : AppColors.success.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      report!.overallRisk
                          ? CupertinoIcons.xmark_shield_fill
                          : CupertinoIcons.checkmark_shield_fill,
                      size: 16,
                      color: report!.overallRisk ? AppColors.danger : AppColors.success,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      report!.overallRisk ? '有风险' : '安全',
                      style: TextStyle(
                        fontSize: 13, fontWeight: FontWeight.w700,
                        color: report!.overallRisk ? AppColors.danger : AppColors.success,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
        const SizedBox(height: 12),
        if (loading)
          const Center(child: CupertinoActivityIndicator(radius: 10))
        else if (report == null)
          const Text('安全数据暂不可用',
              style: TextStyle(fontSize: 13, color: AppColors.textSecondary))
        else
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: report!.items.map((item) {
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: _SecurityTag(item: item),
                );
              }).toList(),
            ),
          ),
      ],
    );

    if (embedded) return content;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(color: Color(0x0A000000), blurRadius: 10, offset: Offset(0, 2)),
        ],
      ),
      child: content,
    );
  }
}

class _SecurityTag extends StatelessWidget {
  final SecurityItem item;
  const _SecurityTag({required this.item});

  @override
  Widget build(BuildContext context) {
    final (icon, color) = switch (item.status) {
      SecurityStatus.safe => (CupertinoIcons.checkmark_shield, AppColors.success),
      SecurityStatus.warning => (CupertinoIcons.exclamationmark_shield, AppColors.warning),
      SecurityStatus.danger => (CupertinoIcons.xmark_shield, AppColors.danger),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.15), width: 0.5),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 5),
          Text('${item.label} ${item.value}',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: color)),
        ],
      ),
    );
  }
}
