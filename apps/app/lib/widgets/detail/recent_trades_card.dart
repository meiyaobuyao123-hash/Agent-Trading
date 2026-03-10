import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import '../../services/gecko_terminal_service.dart';
import '../../theme/app_colors.dart';

/// 逐笔交易列表 — 带规模分类
class RecentTradesCard extends StatefulWidget {
  final String? pairAddress;
  final String network;
  final bool embedded;
  const RecentTradesCard({super.key, this.pairAddress, required this.network, this.embedded = false});

  @override
  State<RecentTradesCard> createState() => _RecentTradesCardState();
}

class _RecentTradesCardState extends State<RecentTradesCard> {
  List<Map<String, dynamic>> _trades = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (widget.pairAddress == null || widget.pairAddress!.isEmpty) {
      setState(() { _loading = false; _error = '无交易对数据'; });
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      final trades = await GeckoTerminalService.instance.fetchTrades(
        network: widget.network, poolAddress: widget.pairAddress!);
      if (mounted) setState(() { _trades = trades; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('最近交易',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600,
                color: AppColors.textPrimary)),
        const SizedBox(height: 12),
        if (_loading)
          const Center(child: CupertinoActivityIndicator(radius: 10))
        else if (_error != null)
          Text(_error!, style: const TextStyle(fontSize: 13, color: AppColors.textSecondary))
        else if (_trades.isEmpty)
          const Text('暂无交易数据',
              style: TextStyle(fontSize: 13, color: AppColors.textSecondary))
        else
          ...List.generate(
            _trades.length > 15 ? 15 : _trades.length,
            (i) => _TradeRow(trade: _trades[i],
                isLast: i == (_trades.length > 15 ? 14 : _trades.length - 1)),
          ),
      ],
    );

    if (widget.embedded) return content;

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

class _TradeRow extends StatelessWidget {
  final Map<String, dynamic> trade;
  final bool isLast;
  const _TradeRow({required this.trade, required this.isLast});

  @override
  Widget build(BuildContext context) {
    final kind = trade['kind'] as String? ?? '';
    final isBuy = kind == 'buy';
    final color = isBuy ? AppColors.success : AppColors.danger;
    final label = isBuy ? '买' : '卖';
    final volumeStr = trade['volume_in_usd'] as String? ?? '0';
    final volumeUsd = double.tryParse(volumeStr) ?? 0;
    final timestamp = trade['block_timestamp'] as String? ?? '';

    // 规模分类
    final sizeLabel = volumeUsd >= 10000 ? '大单' : volumeUsd >= 1000 ? '中单' : '小单';
    final sizeColor = volumeUsd >= 10000 ? AppColors.warning : AppColors.textTertiary;

    String timeStr = '';
    if (timestamp.isNotEmpty) {
      try {
        final dt = DateTime.parse(timestamp);
        final diff = DateTime.now().toUtc().difference(dt);
        if (diff.inMinutes < 60) timeStr = '${diff.inMinutes}m';
        else if (diff.inHours < 24) timeStr = '${diff.inHours}h';
        else timeStr = '${diff.inDays}d';
      } catch (_) {}
    }

    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.03),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Row(
            children: [
              // 买/卖标签
              Container(
                width: 28, height: 22,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(label, style: TextStyle(fontSize: 11,
                    fontWeight: FontWeight.w700, color: color)),
              ),
              const SizedBox(width: 8),
              // 金额
              Text('\$${_fmtVol(volumeUsd)}',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary)),
              const SizedBox(width: 6),
              // 规模
              Text(sizeLabel, style: TextStyle(fontSize: 10, color: sizeColor)),
              const Spacer(),
              // 时间
              if (timeStr.isNotEmpty)
                Text(timeStr, style: const TextStyle(fontSize: 12,
                    color: AppColors.textTertiary)),
            ],
          ),
        ),
        if (!isLast)
          const Divider(height: 0.5, thickness: 0.5, color: Color(0xFFF2F2F7)),
      ],
    );
  }

  String _fmtVol(double v) {
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '${(v / 1e3).toStringAsFixed(1)}K';
    return v.toStringAsFixed(0);
  }
}
