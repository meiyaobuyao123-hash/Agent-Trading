import 'package:flutter/cupertino.dart';
import '../../l10n/app_localizations.dart';
import '../../services/gecko_terminal_service.dart';
import '../../theme/app_colors.dart';

/// Bitget 风格逐笔交易列表
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
  bool _noPairData = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (widget.pairAddress == null || widget.pairAddress!.isEmpty) {
      setState(() { _loading = false; _noPairData = true; });
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
        if (!widget.embedded) ...[
          Text(S.of(context).recentTrades,
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600,
                  color: context.colors.textPrimary)),
          const SizedBox(height: 12),
        ],
        if (_loading)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 20),
            child: Center(child: CupertinoActivityIndicator(radius: 10)),
          )
        else if (_noPairData)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 20),
            child: Center(child: Text(S.of(context).noTradePairData, style: TextStyle(fontSize: 13, color: context.colors.textSecondary))),
          )
        else if (_error != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 20),
            child: Center(child: Text(_error!, style: TextStyle(fontSize: 13, color: context.colors.textSecondary))),
          )
        else if (_trades.isEmpty)
          Padding(
            padding: EdgeInsets.symmetric(vertical: 20),
            child: Center(child: Text(S.of(context).noTradeData,
                style: TextStyle(fontSize: 13, color: context.colors.textSecondary))),
          )
        else
          ...List.generate(
            _trades.length > 20 ? 20 : _trades.length,
            (i) => _BitgetTradeRow(trade: _trades[i]),
          ),
      ],
    );

    if (widget.embedded) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: content,
      );
    }

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

/// Bitget 风格交易行：数量/时间 | 价值/价格 | 地址
class _BitgetTradeRow extends StatelessWidget {
  final Map<String, dynamic> trade;
  const _BitgetTradeRow({required this.trade});

  @override
  Widget build(BuildContext context) {
    final kind = trade['kind'] as String? ?? '';
    final isBuy = kind == 'buy';
    final color = isBuy ? context.colors.success : context.colors.danger;
    final label = isBuy ? S.of(context).buy : S.of(context).sell;

    final volumeUsd = (trade['volume_usd'] as num?)?.toDouble() ?? 0;
    final priceUsd = (trade['price_usd'] as num?)?.toDouble() ?? 0;
    final fromAmt = (trade['from_amount'] as num?)?.toDouble() ?? 0;
    final toAmt = (trade['to_amount'] as num?)?.toDouble() ?? 0;
    final qty = isBuy ? toAmt : fromAmt;

    final timestamp = trade['timestamp'] as String? ?? '';
    final maker = trade['maker'] as String? ?? '';
    final txHash = trade['tx_hash'] as String? ?? '';

    String timeStr = '';
    if (timestamp.isNotEmpty) {
      try {
        final dt = DateTime.parse(timestamp);
        final diff = DateTime.now().toUtc().difference(dt);
        if (diff.inSeconds < 60) {
          timeStr = S.of(context).secondsAgo(diff.inSeconds);
        } else if (diff.inMinutes < 60) {
          timeStr = S.of(context).minutesAgo(diff.inMinutes);
        } else if (diff.inHours < 24) {
          timeStr = S.of(context).hoursAgo(diff.inHours);
        } else {
          timeStr = S.of(context).daysAgo(diff.inDays);
        }
      } catch (_) {}
    }

    // 地址：优先用 maker，退而用 txHash
    final addr = maker.isNotEmpty ? maker : txHash;
    final addrDisplay = addr.length > 10
        ? '${addr.substring(0, 4)}...${addr.substring(addr.length - 4)}'
        : '';

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Color(0xFFF2F2F7), width: 0.5)),
      ),
      child: Row(
        children: [
          // 列1: 买入/卖出 + 数量 + 时间
          Expanded(
            flex: 4,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color)),
                  const SizedBox(width: 4),
                  Flexible(
                    child: Text(
                      '${isBuy ? "+" : "-"}${_fmtQty(qty)}',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: color,
                        fontFeatures: const [FontFeature.tabularFigures()]),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ]),
                if (timeStr.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(timeStr, style: TextStyle(fontSize: 11, color: context.colors.textTertiary)),
                  ),
              ],
            ),
          ),
          // 列2: 价值 + 价格
          Expanded(
            flex: 3,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('\$${_fmtVol(volumeUsd)}',
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: context.colors.textPrimary,
                      fontFeatures: [FontFeature.tabularFigures()])),
                if (priceUsd > 0)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text('\$${_fmtSmallPrice(priceUsd)}',
                        style: TextStyle(fontSize: 11, color: context.colors.textTertiary,
                          fontFeatures: [FontFeature.tabularFigures()])),
                  ),
              ],
            ),
          ),
          // 列3: 地址
          Expanded(
            flex: 3,
            child: Text(addrDisplay,
              style: TextStyle(fontSize: 12, color: context.colors.textPrimary),
              textAlign: TextAlign.right),
          ),
        ],
      ),
    );
  }

  String _fmtQty(double v) {
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '${(v / 1e3).toStringAsFixed(1)}K';
    if (v >= 1) return v.toStringAsFixed(2);
    return v.toStringAsFixed(4);
  }

  String _fmtVol(double v) {
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(1)}M';
    if (v >= 1e3) return '${(v / 1e3).toStringAsFixed(1)}K';
    return v.toStringAsFixed(2);
  }

  String _fmtSmallPrice(double p) {
    if (p >= 1) return p.toStringAsFixed(2);
    if (p >= 0.01) return p.toStringAsFixed(4);
    return p.toStringAsFixed(7);
  }
}
