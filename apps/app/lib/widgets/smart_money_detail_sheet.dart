import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../l10n/app_localizations.dart';
import '../models/smart_money_signal.dart';
import '../models/smart_money_txn.dart';
import '../models/token_detail.dart';
import '../screens/detail/token_detail_page.dart';
import '../services/smart_money_service.dart';
import '../theme/app_colors.dart';
import '../utils/chain_utils.dart';
import '../utils/format_utils.dart';
import 'common/token_avatar.dart';

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
  bool _loading = true;
  String? _error;
  int _tabIndex = 0; // 0 = 买入, 1 = 卖出

  /// 直接从 signal 对象取汇总数据（不依赖后端 API）
  SmartMoneyTxnSummary get _summary {
    final sig = widget.signal;
    return SmartMoneyTxnSummary(
      totalInflow: sig.buyVolume,
      totalOutflow: sig.sellVolume,
      netFlow: sig.buyVolume - sig.sellVolume,
      uniqueBuyers: sig.uniqueBuyers,
      uniqueSellers: sig.uniqueSellers,
      buyCount: sig.buyCount,
      sellCount: sig.sellCount,
    );
  }

  @override
  void initState() {
    super.initState();
    _loadTxns();
  }

  Future<void> _loadTxns() async {
    try {
      final txns = await SmartMoneyService.fetchTxns(
        widget.signal.chain,
        widget.signal.tokenAddress,
      );
      if (mounted) {
        setState(() {
          _allTxns = txns;
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = S.of(context).loadFailed;
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

            // 交易列表 / 分层统计
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _error != null
                      ? Center(
                          child: Text(_error!,
                              style: TextStyle(color: c.textTertiary)))
                      : _filteredTxns.isNotEmpty
                          ? ListView.separated(
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
                            )
                          : _buildTierBreakdown(c, scrollCtrl),
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
          TokenAvatar(imageUrl: ChainUtils.tokenImageUrl(sig.imageUrl, sig.chain, sig.tokenAddress), symbol: sig.tokenSymbol, chain: sig.chain, size: 40, borderWidth: 2),
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
                          : (sig.tokenAddress.length >= 8
                              ? sig.tokenAddress.substring(0, 8)
                              : sig.tokenAddress),
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
                        color: ChainUtils.getColor(sig.chain).withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        sig.chainLabel,
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: ChainUtils.getColor(sig.chain),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  'MC ${sig.marketCapShort}  ·  ${FormatUtils.fmtPrice(sig.priceUsd)}',
                  style: TextStyle(fontSize: 12, color: c.textSecondary),
                ),
              ],
            ),
          ),
          // 查看详情按钮
          GestureDetector(
            onTap: () {
              final nav = Navigator.of(context);
              final detail = _buildDetail();
              nav.pop();
              nav.push(MaterialPageRoute(builder: (_) => TokenDetailPage(token: detail)));
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
                  Text(S.of(context).detail,
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
              label: S.of(context).totalInflow,
              value: FormatUtils.fmtVolume(_summary.totalInflow),
              color: c.success,
            ),
            _divider(c),
            _StatBox(
              label: S.of(context).totalOutflow,
              value: FormatUtils.fmtVolume(_summary.totalOutflow),
              color: c.danger,
            ),
            _divider(c),
            _StatBox(
              label: S.of(context).netFlowLabel,
              value: FormatUtils.fmtVolume(_summary.netFlow.abs()),
              prefix: _summary.netFlow >= 0 ? '+' : '-',
              color: _summary.isNetPositive ? c.success : c.danger,
            ),
            _divider(c),
            _StatBox(
              label: S.of(context).wallet,
              value: S.of(context).buyerSellerCount(_summary.uniqueBuyers, _summary.uniqueSellers),
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
            _tabButton(c, 0, S.of(context).buy, _summary.buyCount, c.success),
            _tabButton(c, 1, S.of(context).sell, _summary.sellCount, c.danger),
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

  /// 当没有单笔交易记录时，展示分层钱包统计
  Widget _buildTierBreakdown(AppColorScheme c, ScrollController scrollCtrl) {
    final sig = widget.signal;
    final isBuyTab = _tabIndex == 0;

    // 分层数据
    final eliteCount = isBuyTab ? sig.eliteBuyCount : sig.eliteSellCount;
    final verifiedCount = isBuyTab ? sig.verifiedBuyCount : sig.verifiedSellCount;
    final totalCount = isBuyTab ? sig.buyCount : sig.sellCount;
    final watchingCount = (totalCount - eliteCount - verifiedCount).clamp(0, totalCount);
    final totalVolume = isBuyTab ? sig.buyVolume : sig.sellVolume;
    final walletCount = isBuyTab ? sig.uniqueBuyers : sig.uniqueSellers;

    final tiers = <_TierData>[
      if (eliteCount > 0)
        _TierData(S.of(context).elite, eliteCount, const Color(0xFFFFB81C)),
      if (verifiedCount > 0)
        _TierData(S.of(context).verified, verifiedCount, const Color(0xFF3B82F6)),
      if (watchingCount > 0)
        _TierData(S.of(context).watching, watchingCount, const Color(0xFF8B95A5)),
    ];

    return ListView(
      controller: scrollCtrl,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      children: [
        // 总览卡片
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: c.textPrimary.withValues(alpha: 0.06),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    isBuyTab ? S.of(context).buyOverview : S.of(context).sellOverview,
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: c.textPrimary,
                    ),
                  ),
                  Text(
                    FormatUtils.fmtVolume(totalVolume),
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                      color: isBuyTab ? c.success : c.danger,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(S.of(context).walletTxInfo(walletCount, totalCount),
                      style: TextStyle(fontSize: 12, color: c.textSecondary)),
                  if (totalCount > 0 && walletCount > 0)
                    Text(
                      S.of(context).avgPerTx(FormatUtils.fmtVolume(totalVolume / totalCount)),
                      style: TextStyle(fontSize: 12, color: c.textSecondary),
                    ),
                ],
              ),
            ],
          ),
        ),

        const SizedBox(height: 12),

        // 分层统计条
        if (tiers.isNotEmpty) ...[
          // 比例条
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: SizedBox(
              height: 8,
              child: Row(
                children: tiers.map((t) {
                  final ratio = totalCount > 0 ? t.count / totalCount : 0.0;
                  return Expanded(
                    flex: (ratio * 1000).round().clamp(1, 1000),
                    child: Container(color: t.color),
                  );
                }).toList(),
              ),
            ),
          ),
          const SizedBox(height: 12),

          // 分层行
          ...tiers.map((t) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Row(
              children: [
                Container(
                  width: 10, height: 10,
                  decoration: BoxDecoration(
                    color: t.color,
                    shape: BoxShape.circle,
                    boxShadow: [BoxShadow(color: t.color.withValues(alpha: 0.3), blurRadius: 4)],
                  ),
                ),
                const SizedBox(width: 10),
                Text(t.label,
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: c.textPrimary)),
                const Spacer(),
                Text(S.of(context).txCount(t.count),
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: t.color)),
                const SizedBox(width: 12),
                SizedBox(
                  width: 48,
                  child: Text(
                    '${(totalCount > 0 ? t.count / totalCount * 100 : 0).toStringAsFixed(0)}%',
                    textAlign: TextAlign.end,
                    style: TextStyle(fontSize: 12, color: c.textSecondary),
                  ),
                ),
              ],
            ),
          )),

          const SizedBox(height: 8),

          // 说明入口
          GestureDetector(
            onTap: () => _showTierExplanation(context, c),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.info_outline_rounded, size: 14, color: c.textTertiary),
                const SizedBox(width: 4),
                Text(S.of(context).learnTier,
                    style: TextStyle(fontSize: 12, color: c.textTertiary)),
              ],
            ),
          ),
        ],
      ],
    );
  }

  void _showTierExplanation(BuildContext context, AppColorScheme c) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
        decoration: BoxDecoration(
          color: c.bgSecondary,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 36, height: 4,
                decoration: BoxDecoration(
                  color: c.textTertiary.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(S.of(context).tierExplanation,
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: c.textPrimary)),
            const SizedBox(height: 14),
            _tierRow(c, S.of(context).elite, const Color(0xFFFFB81C), S.of(context).eliteDesc),
            _tierRow(c, S.of(context).verified, const Color(0xFF3B82F6), S.of(context).verifiedDesc),
            _tierRow(c, S.of(context).watching, const Color(0xFF8B95A5), S.of(context).watchingDesc),
            const SizedBox(height: 12),
            Text(
              S.of(context).tierSystemDesc,
              style: TextStyle(fontSize: 12, color: c.textSecondary, height: 1.5),
            ),
          ],
        ),
      ),
    );
  }

  Widget _tierRow(AppColorScheme c, String label, Color color, String desc) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Container(
            width: 8, height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 8),
          Text(label,
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: color)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(desc,
                style: TextStyle(fontSize: 12, color: c.textSecondary)),
          ),
        ],
      ),
    );
  }

  TokenDetail _buildDetail() {
    final sig = widget.signal;
    return TokenDetail(
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
      ageDays: 0,
      holderCount: 0,
    );
  }

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

// ─── 单笔交易行 ─────────────────────────────────────
class _TxnRow extends StatelessWidget {
  final SmartMoneyTxn txn;
  const _TxnRow({required this.txn});

  String _tierText(BuildContext context, String tier) {
    final t = S.of(context);
    return switch (tier) {
      'elite' => t.elite,
      'verified' => t.verified,
      'watching' => t.watching,
      _ => tier,
    };
  }

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
            content: Text(S.of(context).copied(txn.walletShort)),
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
                          _tierText(context, txn.tierLabel),
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
                  FormatUtils.fmtVolume(txn.volumeUsd),
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: txn.isBuy ? c.success : c.danger,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'MC ${FormatUtils.fmtVolume(txn.marketCapAtTx)}',
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

}

/// 分层统计数据
class _TierData {
  final String label;
  final int count;
  final Color color;
  const _TierData(this.label, this.count, this.color);
}
