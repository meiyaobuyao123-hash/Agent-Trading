import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/app_colors.dart';
import '../services/agent_service.dart';
import '../utils/format_utils.dart';

/// 展示策略交易记录 + P&L 的底部弹窗
void showStrategyDetailSheet(BuildContext context, AgentStrategy strategy) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _StrategyDetailSheet(strategy: strategy),
  );
}

class _StrategyDetailSheet extends StatefulWidget {
  final AgentStrategy strategy;
  const _StrategyDetailSheet({required this.strategy});

  @override
  State<_StrategyDetailSheet> createState() => _StrategyDetailSheetState();
}

class _StrategyDetailSheetState extends State<_StrategyDetailSheet> {
  bool _loading = true;
  bool _error = false;
  List<AgentExecution> _executions = [];
  ExecutionSummary _summary = const ExecutionSummary();
  String _filter = 'all'; // all / buy / sell

  @override
  void initState() {
    super.initState();
    _loadExecutions();
  }

  Future<void> _loadExecutions() async {
    setState(() {
      _loading = true;
      _error = false;
    });
    final resp =
        await AgentService.instance.listExecutions(widget.strategy.id);
    if (!mounted) return;
    setState(() {
      if (resp != null) {
        _executions = resp.executions;
        _summary = resp.summary;
      } else {
        _error = true;
      }
      _loading = false;
    });
  }

  List<AgentExecution> get _filteredExecs {
    if (_filter == 'all') return _executions;
    return _executions.where((e) => e.action == _filter).toList();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return DraggableScrollableSheet(
      initialChildSize: 0.75,
      maxChildSize: 0.95,
      minChildSize: 0.4,
      builder: (ctx, scrollCtrl) => Container(
        decoration: BoxDecoration(
          color: c.bgSecondary,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Column(
          children: [
            // ── 拖拽手柄 ──
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Container(
                width: 40, height: 4,
                decoration: BoxDecoration(
                  color: c.textTertiary.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),

            // ── 策略头部 ──
            _SheetHeader(strategy: widget.strategy),

            const SizedBox(height: 12),

            // ── P&L 汇总 ──
            if (!_loading)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: _PnlSummary(summary: _summary),
              ),

            const SizedBox(height: 12),

            // ── 筛选标签 ──
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: _FilterTabs(
                selected: _filter,
                summary: _summary,
                onChanged: (v) => setState(() => _filter = v),
              ),
            ),

            const SizedBox(height: 8),

            // ── 交易列表 ──
            Expanded(
              child: _loading
                  ? Center(
                      child: CircularProgressIndicator(
                          color: c.primary, strokeWidth: 2))
                  : _error
                      ? Center(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.cloud_off_rounded,
                                  size: 48, color: c.textTertiary),
                              const SizedBox(height: 12),
                              Text('加载失败',
                                  style: TextStyle(
                                      color: c.textTertiary, fontSize: 14)),
                              const SizedBox(height: 8),
                              TextButton(
                                onPressed: _loadExecutions,
                                child: Text('点击重试',
                                    style: TextStyle(color: c.primary)),
                              ),
                            ],
                          ),
                        )
                      : _filteredExecs.isEmpty
                          ? _EmptyState(filter: _filter)
                          : ListView.builder(
                              controller: scrollCtrl,
                              padding: const EdgeInsets.symmetric(horizontal: 16),
                              itemCount: _filteredExecs.length,
                              itemBuilder: (_, i) => _ExecutionRow(
                                execution: _filteredExecs[i],
                              ),
                            ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─── 策略头部 ─────────────────────────────────────────────
class _SheetHeader extends StatelessWidget {
  final AgentStrategy strategy;
  const _SheetHeader({required this.strategy});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final isActive = strategy.isActive;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          Container(
            width: 40, height: 40,
            decoration: BoxDecoration(
              color: c.primaryLight,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(Icons.auto_graph_rounded, color: c.primary, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        strategy.name,
                        style: TextStyle(
                          color: c.textPrimary,
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          letterSpacing: -0.3,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: isActive ? c.successLight : c.surfaceAlt,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        isActive ? '运行中' : '已暂停',
                        style: TextStyle(
                          color: isActive ? c.success : c.textTertiary,
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  '${strategy.triggerCount}次触发 · ${strategy.cooldownMin}分钟冷却',
                  style: TextStyle(fontSize: 11, color: c.textTertiary),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─── P&L 汇总面板 ──────────────────────────────────────────
class _PnlSummary extends StatelessWidget {
  final ExecutionSummary summary;
  const _PnlSummary({required this.summary});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;

    if (!summary.hasTrades) {
      return Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: c.cardGlass,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: c.glassBorder, width: 0.5),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.info_outline_rounded, size: 16, color: c.textTertiary),
            const SizedBox(width: 8),
            Text(
              '暂无交易记录',
              style: TextStyle(color: c.textTertiary, fontSize: 13),
            ),
          ],
        ),
      );
    }

    final pnlColor = summary.isProfit ? c.success : c.danger;
    final pnlPrefix = summary.isProfit ? '+' : '';
    final roi = summary.totalBuyUsd > 0
        ? (summary.realizedPnl / summary.totalBuyUsd * 100)
        : 0.0;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: c.cardGlass,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: c.glassBorder, width: 0.5),
      ),
      child: Column(
        children: [
          // 顶行: 已实现收益
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('已实现收益',
                  style: TextStyle(color: c.textTertiary, fontSize: 11)),
            ],
          ),
          const SizedBox(height: 4),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                '$pnlPrefix\$${summary.realizedPnl.abs().toStringAsFixed(2)}',
                style: TextStyle(
                  color: pnlColor,
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.5,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: pnlColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '$pnlPrefix${roi.toStringAsFixed(1)}%',
                  style: TextStyle(
                    color: pnlColor,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // 底行: 4个统计格
          Row(
            children: [
              _StatCell(
                label: '买入',
                value: '\$${FormatUtils.fmtAmtRaw(summary.totalBuyUsd)}',
                color: c.danger,
              ),
              _StatCell(
                label: '卖出',
                value: '\$${FormatUtils.fmtAmtRaw(summary.totalSellUsd)}',
                color: c.success,
              ),
              _StatCell(
                label: 'Gas',
                value: '\$${FormatUtils.fmtAmtRaw(summary.totalGasUsd)}',
                color: c.warning,
              ),
              _StatCell(
                label: '成功率',
                value: summary.totalCount > 0
                    ? '${(summary.confirmedCount / summary.totalCount * 100).toStringAsFixed(0)}%'
                    : '-',
                color: c.primary,
              ),
            ],
          ),
        ],
      ),
    );
  }

}

class _StatCell extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _StatCell({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Expanded(
      child: Column(
        children: [
          Text(label, style: TextStyle(color: c.textTertiary, fontSize: 10)),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 13,
              fontWeight: FontWeight.w700,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}

// ─── 筛选标签 ──────────────────────────────────────────────
class _FilterTabs extends StatelessWidget {
  final String selected;
  final ExecutionSummary summary;
  final ValueChanged<String> onChanged;
  const _FilterTabs({
    required this.selected,
    required this.summary,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Row(
      children: [
        _TabChip(
          label: '全部 ${summary.totalCount}',
          active: selected == 'all',
          onTap: () => onChanged('all'),
        ),
        const SizedBox(width: 6),
        _TabChip(
          label: '买入 ${summary.buyCount}',
          active: selected == 'buy',
          activeColor: c.danger,
          onTap: () => onChanged('buy'),
        ),
        const SizedBox(width: 6),
        _TabChip(
          label: '卖出 ${summary.sellCount}',
          active: selected == 'sell',
          activeColor: c.success,
          onTap: () => onChanged('sell'),
        ),
      ],
    );
  }
}

class _TabChip extends StatelessWidget {
  final String label;
  final bool active;
  final Color? activeColor;
  final VoidCallback onTap;
  const _TabChip({
    required this.label,
    required this.active,
    this.activeColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final color = activeColor ?? c.primary;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: active ? color.withValues(alpha: 0.15) : c.surfaceAlt,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: active ? color.withValues(alpha: 0.3) : c.border,
            width: 0.5,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: active ? color : c.textTertiary,
            fontSize: 12,
            fontWeight: active ? FontWeight.w600 : FontWeight.w500,
          ),
        ),
      ),
    );
  }
}

// ─── 单笔交易行 ───────────────────────────────────────────
class _ExecutionRow extends StatelessWidget {
  final AgentExecution execution;
  const _ExecutionRow({required this.execution});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final isBuy = execution.isBuy;
    final actionColor = isBuy ? c.danger : c.success;
    final statusColor = execution.isConfirmed
        ? c.success
        : execution.isFailed
            ? c.danger
            : c.warning;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: c.cardGlass,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: c.glassBorder, width: 0.5),
      ),
      child: Column(
        children: [
          // 第1行: 买/卖 + 链 + 地址 + 时间
          Row(
            children: [
              // 买/卖标签
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: actionColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  isBuy ? '买入' : '卖出',
                  style: TextStyle(
                    color: actionColor,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(width: 6),
              // 链标签
              if (execution.chain != null) ...[
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                  decoration: BoxDecoration(
                    color: c.primaryLight,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    execution.chainLabel,
                    style: TextStyle(
                      color: c.primary,
                      fontSize: 9,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(width: 6),
              ],
              // 地址
              GestureDetector(
                onTap: () {
                  if (execution.tokenAddress != null) {
                    Clipboard.setData(
                        ClipboardData(text: execution.tokenAddress!));
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: const Text('地址已复制'),
                        duration: const Duration(seconds: 1),
                        behavior: SnackBarBehavior.floating,
                      ),
                    );
                  }
                },
                child: Text(
                  execution.addressShort,
                  style: TextStyle(
                    color: c.primary,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              const Spacer(),
              // 状态
              Container(
                width: 6, height: 6,
                decoration: BoxDecoration(
                  color: statusColor,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                execution.statusLabel,
                style: TextStyle(
                  color: statusColor,
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          // 第2行: 金额 + 价格 + Gas + 时间
          Row(
            children: [
              // 金额
              _InfoTag(
                icon: Icons.attach_money,
                label: FormatUtils.fmtAmt(execution.amountUsd),
                color: c.textPrimary,
              ),
              const SizedBox(width: 10),
              // 成交价
              if (execution.executedPrice > 0)
                _InfoTag(
                  icon: Icons.show_chart,
                  label: FormatUtils.fmtPrice(execution.executedPrice),
                  color: c.textSecondary,
                ),
              const Spacer(),
              // Gas
              if (execution.gasFeeUsd > 0) ...[
                Text(
                  'Gas \$${execution.gasFeeUsd.toStringAsFixed(4)}',
                  style: TextStyle(
                    color: c.textTertiary,
                    fontSize: 10,
                  ),
                ),
                const SizedBox(width: 8),
              ],
              // 时间
              Text(
                execution.timeAgo,
                style: TextStyle(color: c.textTertiary, fontSize: 10),
              ),
            ],
          ),
          // 第3行: txHash（如果有）
          if (execution.txHash != null && execution.txHash!.isNotEmpty) ...[
            const SizedBox(height: 6),
            GestureDetector(
              onTap: () {
                Clipboard.setData(ClipboardData(text: execution.txHash!));
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: const Text('交易哈希已复制'),
                    duration: const Duration(seconds: 1),
                    behavior: SnackBarBehavior.floating,
                  ),
                );
              },
              child: Row(
                children: [
                  Icon(Icons.receipt_long_outlined,
                      size: 11, color: c.textTertiary),
                  const SizedBox(width: 4),
                  Text(
                    FormatUtils.truncHash(execution.txHash!),
                    style: TextStyle(
                      color: c.textTertiary,
                      fontSize: 10,
                      fontFamily: 'monospace',
                    ),
                  ),
                  const SizedBox(width: 4),
                  Icon(Icons.copy_rounded, size: 10, color: c.textTertiary),
                ],
              ),
            ),
          ],
          // 错误信息
          if (execution.isFailed && execution.errorMessage != null) ...[
            const SizedBox(height: 6),
            Row(
              children: [
                Icon(Icons.error_outline, size: 11, color: c.danger),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    execution.errorMessage!,
                    style: TextStyle(color: c.danger, fontSize: 10),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

}

class _InfoTag extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  const _InfoTag({
    required this.icon,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 12, color: color),
        const SizedBox(width: 3),
        Text(
          label,
          style: TextStyle(
            color: color,
            fontSize: 12,
            fontWeight: FontWeight.w600,
            fontFeatures: const [FontFeature.tabularFigures()],
          ),
        ),
      ],
    );
  }
}

// ─── 空状态 ────────────────────────────────────────────────
class _EmptyState extends StatelessWidget {
  final String filter;
  const _EmptyState({required this.filter});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final label = filter == 'buy'
        ? '暂无买入记录'
        : filter == 'sell'
            ? '暂无卖出记录'
            : '暂无交易记录';
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.swap_vert_rounded, size: 48, color: c.textTertiary),
          const SizedBox(height: 12),
          Text(
            label,
            style: TextStyle(color: c.textTertiary, fontSize: 14),
          ),
          const SizedBox(height: 6),
          Text(
            '当策略触发交易后，记录将在这里展示',
            style: TextStyle(color: c.textTertiary, fontSize: 12),
          ),
        ],
      ),
    );
  }
}
