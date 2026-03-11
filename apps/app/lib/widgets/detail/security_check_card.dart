import 'package:flutter/cupertino.dart';
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
            Text('安全检测',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600,
                    color: context.colors.textPrimary)),
            const Spacer(),
            if (report != null)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: report!.overallRisk
                      ? context.colors.danger.withValues(alpha: 0.1)
                      : context.colors.success.withValues(alpha: 0.1),
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
                      color: report!.overallRisk ? context.colors.danger : context.colors.success,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      report!.overallRisk ? '有风险' : '安全',
                      style: TextStyle(
                        fontSize: 13, fontWeight: FontWeight.w700,
                        color: report!.overallRisk ? context.colors.danger : context.colors.success,
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
          Text('安全数据暂不可用',
              style: TextStyle(fontSize: 13, color: context.colors.textSecondary))
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
        color: context.colors.cardGlass,
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
      SecurityStatus.safe => (CupertinoIcons.checkmark_shield, context.colors.success),
      SecurityStatus.warning => (CupertinoIcons.exclamationmark_shield, context.colors.warning),
      SecurityStatus.danger => (CupertinoIcons.xmark_shield, context.colors.danger),
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
