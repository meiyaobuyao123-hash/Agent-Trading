import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/smart_money_signal.dart';
import '../models/smart_money_txn.dart';
import '../models/token_detail.dart';
import '../screens/detail/token_detail_page.dart';
import '../services/smart_money_service.dart';
import '../theme/app_colors.dart';

/// 显示聪明钱买卖详情底部弹窗
Future<void> showSmartMoneyDetailSheet(
  BuildContext context,
  SmartMoneySignal signal,
) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _SmartMoneyDetailSheet(signal: signal),
  );
}

class _SmartMoneyDetailSheet extends StatefulWidget {
  final SmartMoneySignal signal;
  const _SmartMoneyDetailSheet({required this.signal});

  @override
  State<_SmartMoneyDetailSheet> createState() => _SmartMoneyDetailSheetState();
}

class _SmartMoneyDetailSheetState extends State<_SmartMoneyDetailSheet> {
  List<SmartMoneyTxn> _allTxns = [];
  SmartMoneyTxnSummary _summary = const SmartMoneyTxnSummary();
  bool _loading = true;
  String? _error;
  int _tabIndex = 0; // 0 = 买入, 1 = 卖出

  @override
  void initState() {
    super.initState();
    _loadTxns();
  }

  Future<void> _loadTxns() async {
    try {
      final result = await SmartMoneyService.fetchTxns(
        widget.signal.chain,
        widget.signal.tokenAddress,
      );
      if (mounted) {
        setState(() {
          _allTxns = result.txns;
          _summary = result.summary;
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '加载失败';
          _loading = false;
        });
      }
    }
  }

  List<SmartMoneyTxn> get _filteredTxns {
    final type = _tabIndex == 0 ? 'buy' : 'sell';
    return _allTxns.where((t) => t.txType == type).toList();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return DraggableScrollableSheet(
      initialChildSize: 0.72,
      maxChildSize: 0.95,
      minChildSize: 0.4,
      builder: (_, scrollCtrl) => Container(
        decoration: BoxDecoration(
          color: c.bgSecondary,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        ),
        child: Column(
          children: [
            // 拖拽指示条
            Padding(
              padding: const EdgeInsets.only(top: 10, bottom: 6),
              child: Container(
                width: 40, height: 4,
                decoration: BoxDecoration(
                  color: c.textTertiary.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),

            // Header
            _buildHeader(c),

            const SizedBox(height: 10),

            // 流量汇总
            _buildFlowSummary(c),

            const SizedBox(height: 12),

            // Tab 切换: 买入 / 卖出
            _buildTabToggle(c),

            const SizedBox(height: 8),

            // 交易列表
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _error != null
                      ? Center(
                          child: Text(_error!,
                              style: TextStyle(color: c.textTertiary)))
                      : _filteredTxns.isEmpty
                          ? Center(
                              child: Text(
                                _tabIndex == 0 ? '暂无买入记录' : '暂无卖出记录',
                                style: TextStyle(
                                    color: c.textTertiary, fontSize: 14),
                              ),
                            )
                          : ListView.separated(
                              controller: scrollCtrl,
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 16, vertical: 4),
                              itemCount: _filteredTxns.length,
                              separatorBuilder: (_, __) => Divider(
                                height: 1,
                                color: c.textTertiary.withValues(alpha: 0.1),
                              ),
                              itemBuilder: (_, i) =>
                                  _TxnRow(txn: _filteredTxns[i]),
                            ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(AppColorScheme c) {
    final sig = widget.signal;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          // 头像
          _TokenAvatar(signal: sig, size: 40),
          const SizedBox(width: 10),
          // 名称 + 链
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      sig.tokenSymbol.isNotEmpty
                          ? sig.tokenSymbol.toUpperCase()
                          : sig.tokenAddress.substring(0, 8),
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        color: c.textPrimary,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 5, vertical: 2),
                      decoration: BoxDecoration(
                        color: _chainColor(sig.chain).withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        sig.chainLabel,
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: _chainColor(sig.chain),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  'MC ${sig.marketCapShort}  ·  ${_fmtPrice(sig.priceUsd)}',
                  style: TextStyle(fontSize: 12, color: c.textSecondary),
                ),
              ],
            ),
          ),
          // 查看详情按钮
          GestureDetector(
            onTap: () {
              Navigator.pop(context);
              _navigateToDetail(context);
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: c.primary.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('详情',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: c.primary,
                      )),
                  Icon(Icons.chevron_right, size: 16, color: c.primary),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFlowSummary(AppColorScheme c) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
        decoration: BoxDecoration(
          color: c.surface.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
              color: c.textTertiary.withValues(alpha: 0.08), width: 0.5),
        ),
        child: Row(
          children: [
            _StatBox(
              label: '总流入',
              value: _fmtVolume(_summary.totalInflow),
              color: c.success,
            ),
            _divider(c),
            _StatBox(
              label: '总流出',
              value: _fmtVolume(_summary.totalOutflow),
              color: c.danger,
            ),
            _divider(c),
            _StatBox(
              label: '净流向',
              value: _fmtVolume(_summary.netFlow.abs()),
              prefix: _summary.netFlow >= 0 ? '+' : '-',
              color: _summary.isNetPositive ? c.success : c.danger,
            ),
            _divider(c),
            _StatBox(
              label: '钱包',
              value: '${_summary.uniqueBuyers}买/${_summary.uniqueSellers}卖',
              color: c.textPrimary,
            ),
          ],
        ),
      ),
    );
  }

  Widget _divider(AppColorScheme c) => Container(
        width: 1,
        height: 28,
        margin: const EdgeInsets.symmetric(horizontal: 6),
        color: c.textTertiary.withValues(alpha: 0.1),
      );

  Widget _buildTabToggle(AppColorScheme c) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Container(
        height: 36,
        decoration: BoxDecoration(
          color: c.surface.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          children: [
            _tabButton(c, 0, '买入', _summary.buyCount, c.success),
            _tabButton(c, 1, '卖出', _summary.sellCount, c.danger),
          ],
        ),
      ),
    );
  }

  Widget _tabButton(
      AppColorScheme c, int index, String label, int count, Color color) {
    final selected = _tabIndex == index;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _tabIndex = index),
        child: Container(
          margin: const EdgeInsets.all(3),
          decoration: BoxDecoration(
            color: selected ? color.withValues(alpha: 0.15) : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
          ),
          alignment: Alignment.center,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                  color: selected ? color : c.textTertiary,
                ),
              ),
              const SizedBox(width: 4),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                decoration: BoxDecoration(
                  color: selected
                      ? color.withValues(alpha: 0.2)
                      : c.textTertiary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '$count',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    color: selected ? color : c.textTertiary,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _navigateToDetail(BuildContext context) {
    final sig = widget.signal;
    final detail = TokenDetail(
      source: TokenSource.hotCoin,
      chain: sig.chain,
      address: sig.tokenAddress,
      name: sig.tokenName,
      symbol: sig.tokenSymbol,
      priceUsd: sig.priceUsd,
      marketCapUsd: sig.marketCapUsd,
      liquidityUsd: sig.liquidityUsd,
      volume1hUsd: 0,
      volume24hUsd: sig.volume24hUsd,
      priceChange1h: sig.priceChange1h,
      priceChange6h: 0,
      priceChange24h: sig.priceChange24h,
      buys1h: 0,
      sells1h: 0,
      buys24h: 0,
      sells24h: 0,
      top10HolderPct: 0,
      top1HolderPct: 0,
      goplusRisk: false,
      hasTwitter: false,
      hasTelegram: false,
      hasWebsite: false,
      score: sig.heatScore,
      recommendation: sig.signalStrength,
      imageUri: sig.imageUrl,
      pairAddress: sig.pairAddress,
      dexId: sig.dexId,
    );
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => TokenDetailPage(token: detail)),
    );
  }

  String _fmtPrice(double p) {
    if (p >= 1000) return '\$${p.toStringAsFixed(0)}';
    if (p >= 1) return '\$${p.toStringAsFixed(2)}';
    if (p >= 0.01) return '\$${p.toStringAsFixed(4)}';
    if (p >= 0.0001) return '\$${p.toStringAsFixed(6)}';
    return '\$${p.toStringAsFixed(8)}';
  }

  String _fmtVolume(double v) {
    if (v >= 1e6) return '\$${(v / 1e6).toStringAsFixed(2)}M';
    if (v >= 1e4) return '\$${(v / 1e4).toStringAsFixed(2)}万';
    if (v >= 1e3) return '\$${(v / 1e3).toStringAsFixed(1)}K';
    return '\$${v.toStringAsFixed(0)}';
  }

  Color _chainColor(String chain) => switch (chain) {
        'solana' => const Color(0xFF9945FF),
        'bsc' => const Color(0xFFF3BA2F),
        'base' => const Color(0xFF0052FF),
        'eth' => const Color(0xFF627EEA),
        _ => const Color(0xFF3B82F6),
      };
}

// ─── 统计框 ─────────────────────────────────────────
class _StatBox extends StatelessWidget {
  final String label;
  final String value;
  final String prefix;
  final Color color;

  const _StatBox({
    required this.label,
    required this.value,
    this.prefix = '',
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Expanded(
      child: Column(
        children: [
          Text(label,
              style: TextStyle(fontSize: 10, color: c.textTertiary)),
          const SizedBox(height: 3),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              '$prefix$value',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: color,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─── 代币头像（Sheet用，稍大版本）────────────────────
class _TokenAvatar extends StatelessWidget {
  final SmartMoneySignal signal;
  final double size;
  const _TokenAvatar({required this.signal, required this.size});

  Color get _chainColor => switch (signal.chain) {
        'solana' => const Color(0xFF9945FF),
        'bsc' => const Color(0xFFF3BA2F),
        'base' => const Color(0xFF0052FF),
        'eth' => const Color(0xFF627EEA),
        _ => const Color(0xFF3B82F6),
      };

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(
            color: _chainColor.withValues(alpha: 0.25), width: 2),
      ),
      child: signal.imageUrl != null && signal.imageUrl!.isNotEmpty
          ? ClipRRect(
              borderRadius: BorderRadius.circular(size / 2),
              child: Image.network(
                signal.imageUrl!,
                width: size,
                height: size,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => _letterFallback(),
              ),
            )
          : _letterFallback(),
    );
  }

  Widget _letterFallback() {
    final letter = signal.tokenSymbol.isNotEmpty
        ? signal.tokenSymbol[0].toUpperCase()
        : '?';
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: _chainColor.withValues(alpha: 0.12),
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        letter,
        style: TextStyle(
          color: _chainColor,
          fontSize: size * 0.4,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

// ─── 单笔交易行 ─────────────────────────────────────
class _TxnRow extends StatelessWidget {
  final SmartMoneyTxn txn;
  const _TxnRow({required this.txn});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final tierColor = switch (txn.walletTier) {
      'elite' => const Color(0xFFFFB81C),
      'verified' => const Color(0xFF3B82F6),
      _ => c.textTertiary,
    };

    return InkWell(
      onTap: () {
        Clipboard.setData(ClipboardData(text: txn.walletAddress));
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('已复制 ${txn.walletShort}'),
            duration: const Duration(seconds: 1),
            behavior: SnackBarBehavior.floating,
          ),
        );
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(
          children: [
            // Tier 圆点
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: tierColor,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: tierColor.withValues(alpha: 0.4),
                    blurRadius: 4,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            // 钱包地址 + 时间
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        txn.walletShort,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: c.textPrimary,
                          fontFeatures: const [FontFeature.tabularFigures()],
                        ),
                      ),
                      const SizedBox(width: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 4, vertical: 1),
                        decoration: BoxDecoration(
                          color: tierColor.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(3),
                        ),
                        child: Text(
                          txn.tierLabel,
                          style: TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.w700,
                            color: tierColor,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    txn.timeAgo,
                    style: TextStyle(fontSize: 11, color: c.textTertiary),
                  ),
                ],
              ),
            ),
            // 金额 + 当时MC
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  _fmtVolume(txn.volumeUsd),
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: txn.isBuy ? c.success : c.danger,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'MC ${_fmtMC(txn.marketCapAtTx)}',
                  style: TextStyle(fontSize: 10, color: c.textTertiary),
                ),
              ],
            ),
            const SizedBox(width: 8),
            // 复制图标
            Icon(Icons.copy_rounded, size: 14,
                color: c.textTertiary.withValues(alpha: 0.5)),
          ],
        ),
      ),
    );
  }

  String _fmtVolume(double v) {
    if (v >= 1e6) return '\$${(v / 1e6).toStringAsFixed(2)}M';
    if (v >= 1e4) return '\$${(v / 1e4).toStringAsFixed(2)}万';
    if (v >= 1e3) return '\$${(v / 1e3).toStringAsFixed(1)}K';
    if (v > 0) return '\$${v.toStringAsFixed(2)}';
    return '\$0';
  }

  String _fmtMC(double mc) {
    if (mc >= 1e6) return '\$${(mc / 1e6).toStringAsFixed(2)}M';
    if (mc >= 1e4) return '\$${(mc / 1e4).toStringAsFixed(2)}万';
    if (mc >= 1e3) return '\$${(mc / 1e3).toStringAsFixed(1)}K';
    return '\$${mc.toStringAsFixed(0)}';
  }
}
