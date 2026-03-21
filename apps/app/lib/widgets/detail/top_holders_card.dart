import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../theme/app_colors.dart';
import '../../l10n/app_localizations.dart';

/// Top Holders 持仓排名卡片
/// 显示代币 Top 10 持仓地址及其占比
class TopHoldersCard extends StatelessWidget {
  final List<Map<String, dynamic>> holders;
  final bool embedded;

  const TopHoldersCard({
    super.key,
    required this.holders,
    this.embedded = false,
  });

  @override
  Widget build(BuildContext context) {
    if (holders.isEmpty) {
      return const SizedBox.shrink();
    }

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 标题
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Row(
            children: [
              Icon(Icons.people_outline, size: 18, color: context.colors.textSecondary),
              const SizedBox(width: 6),
              Text(
                S.of(context).topHolders,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: context.colors.textPrimary,
                ),
              ),
              const Spacer(),
              Text(
                'Top ${holders.length}',
                style: TextStyle(fontSize: 12, color: context.colors.textSecondary),
              ),
            ],
          ),
        ),
        // 列表头
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(
            children: [
              SizedBox(width: 28, child: Text('#',
                  style: TextStyle(fontSize: 11, color: context.colors.textSecondary))),
              Expanded(
                flex: 5,
                child: Text(S.of(context).addressLabel,
                    style: TextStyle(fontSize: 11, color: context.colors.textSecondary)),
              ),
              Expanded(
                flex: 3,
                child: Text(S.of(context).holdingPct,
                    textAlign: TextAlign.right,
                    style: TextStyle(fontSize: 11, color: context.colors.textSecondary)),
              ),
              const SizedBox(width: 24), // 占比条空间
            ],
          ),
        ),
        // 列表
        ...holders.asMap().entries.map((entry) {
          final i = entry.key;
          final h = entry.value;
          final rank = h['rank'] ?? (i + 1);
          final wallet = h['wallet'] as String? ?? '';
          final pct = (h['pct'] as num?)?.toDouble() ?? 0.0;
          final shortAddr = wallet.length > 10
              ? '${wallet.substring(0, 6)}...${wallet.substring(wallet.length - 4)}'
              : wallet;

          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 5),
            child: Row(
              children: [
                SizedBox(
                  width: 28,
                  child: Text(
                    '$rank',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: rank <= 3 ? FontWeight.w700 : FontWeight.w400,
                      color: rank <= 3
                          ? const Color(0xFFF59E0B)
                          : context.colors.textSecondary,
                    ),
                  ),
                ),
                Expanded(
                  flex: 5,
                  child: GestureDetector(
                    onTap: () {
                      Clipboard.setData(ClipboardData(text: wallet));
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(S.of(context).addressCopied),
                          duration: const Duration(seconds: 1),
                        ),
                      );
                    },
                    child: Row(
                      children: [
                        Text(
                          shortAddr,
                          style: TextStyle(
                            fontSize: 13,
                            color: context.colors.textPrimary,
                            fontFamily: 'monospace',
                          ),
                        ),
                        const SizedBox(width: 4),
                        Icon(Icons.copy, size: 12, color: context.colors.textSecondary),
                      ],
                    ),
                  ),
                ),
                Expanded(
                  flex: 3,
                  child: Text(
                    '${pct.toStringAsFixed(2)}%',
                    textAlign: TextAlign.right,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: pct > 10
                          ? const Color(0xFFEF4444)
                          : context.colors.textPrimary,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                SizedBox(
                  width: 40,
                  height: 6,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(3),
                    child: LinearProgressIndicator(
                      value: (pct / 100).clamp(0.0, 1.0),
                      backgroundColor: context.colors.cardGlass,
                      valueColor: AlwaysStoppedAnimation(
                        pct > 10 ? const Color(0xFFEF4444) : const Color(0xFF3B82F6),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          );
        }),
      ],
    );

    if (embedded) return content;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(12),
      ),
      child: content,
    );
  }
}
