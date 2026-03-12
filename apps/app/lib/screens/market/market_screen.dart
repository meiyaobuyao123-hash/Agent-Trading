import 'dart:async';
import 'dart:ui';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import '../../models/hot_coin.dart';
import '../../models/daily_pick.dart';
import '../../models/smart_money_signal.dart';
import '../../models/token_detail.dart';
import '../../services/supabase_service.dart';
import '../../services/price_ticker_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/hot_coin_card.dart';
import '../../widgets/pick_card.dart';
import '../../widgets/smart_money_card.dart';
import '../../widgets/shimmer_list.dart';
import '../detail/token_detail_page.dart';

class MarketScreen extends StatefulWidget {
  const MarketScreen({super.key});

  @override
  State<MarketScreen> createState() => _MarketScreenState();
}

class _MarketScreenState extends State<MarketScreen> {
  int _segment = 0;

  List<HotCoin> _hotCoins = [];
  List<HotCoin> _hotFiltered = [];
  bool _hotLoading = true;
  String? _hotError;
  int _chainIndex = 0;
  static const _chainKeys = [null, 'SOL', 'BSC', 'BASE', 'ETH'];

  Map<String, PriceTick> _livePrices = {};
  StreamSubscription? _priceSub;

  List<DailyPick> _picks = [];
  bool _picksLoading = true;
  String? _picksError;

  List<SmartMoneySignal> _smartSignals = [];
  List<SmartMoneySignal> _smartFiltered = [];
  bool _smartLoading = true;
  String? _smartError;
  int _smartChainIndex = 0;
  static const _smartChainKeys = [null, 'solana', 'eth', 'bsc', 'base'];

  @override
  void initState() {
    super.initState();
    _loadHot();
    _loadPicks();
    _loadSmartMoney();
    _priceSub = PriceTickerService.instance.stream.listen((prices) {
      if (mounted) setState(() => _livePrices = prices);
    });
  }

  @override
  void dispose() {
    _priceSub?.cancel();
    PriceTickerService.instance.stop();
    super.dispose();
  }

  Future<void> _loadHot() async {
    if (!_hotLoading) setState(() { _hotLoading = true; _hotError = null; });
    try {
      final coins = await SupabaseService.instance.fetchHotCoins(limit: 50);
      if (mounted) {
        setState(() {
          _hotCoins = coins;
          _hotLoading = false;
          _applyChainFilter();
        });
        PriceTickerService.instance.start(coins.map((c) => c.address).toList());
      }
    } catch (e) {
      if (mounted) setState(() { _hotError = e.toString(); _hotLoading = false; });
    }
  }

  Future<void> _loadPicks() async {
    if (!_picksLoading) setState(() { _picksLoading = true; _picksError = null; });
    try {
      final picks = await SupabaseService.instance.fetchTodayPicks();
      if (mounted) setState(() { _picks = picks; _picksLoading = false; });
    } catch (e) {
      if (mounted) setState(() { _picksError = e.toString(); _picksLoading = false; });
    }
  }

  void _applyChainFilter() {
    final key = _chainKeys[_chainIndex];
    if (key == null) {
      _hotFiltered = List.from(_hotCoins);
    } else {
      _hotFiltered = _hotCoins.where((c) => c.chainLabel == key).toList();
    }
  }

  int _chainCount(String? key) {
    if (key == null) return _hotCoins.length;
    return _hotCoins.where((c) => c.chainLabel == key).length;
  }

  void _openHotDetail(HotCoin coin) {
    Navigator.push(context,
      CupertinoPageRoute(builder: (_) => TokenDetailPage(token: TokenDetail.fromHotCoin(coin))));
  }

  void _openPickDetail(DailyPick pick) {
    Navigator.push(context,
      CupertinoPageRoute(builder: (_) => TokenDetailPage(token: TokenDetail.fromDailyPick(pick))));
  }

  Future<void> _loadSmartMoney() async {
    if (!_smartLoading) setState(() { _smartLoading = true; _smartError = null; });
    try {
      final signals = await SupabaseService.instance.fetchSmartMoneySignals(limit: 50);
      if (mounted) {
        setState(() {
          _smartSignals = signals;
          _smartLoading = false;
          _applySmartChainFilter();
        });
      }
    } catch (e) {
      if (mounted) setState(() { _smartError = e.toString(); _smartLoading = false; });
    }
  }

  void _applySmartChainFilter() {
    final key = _smartChainKeys[_smartChainIndex];
    if (key == null) {
      _smartFiltered = List.from(_smartSignals);
    } else {
      _smartFiltered = _smartSignals.where((s) => s.chain == key).toList();
    }
  }

  int _smartChainCount(String? key) {
    if (key == null) return _smartSignals.length;
    return _smartSignals.where((s) => s.chain == key).length;
  }

  void _openSmartMoneyDetail(SmartMoneySignal sig) {
    // Navigate to token detail page using smart money signal data
    final detail = TokenDetail(
      source: TokenSource.hotCoin,
      chain: sig.chain,
      address: sig.tokenAddress,
      name: sig.tokenName,
      symbol: sig.tokenSymbol,
      priceUsd: sig.priceUsd,
      marketCapUsd: sig.marketCapUsd,
      liquidityUsd: sig.liquidityUsd,
      volume24hUsd: sig.volume24hUsd,
      priceChange24h: sig.priceChange24h,
      priceChange1h: sig.priceChange1h,
      imageUri: sig.imageUrl,
      pairAddress: sig.pairAddress,
      dexId: sig.dexId,
    );
    Navigator.push(context,
      CupertinoPageRoute(builder: (_) => TokenDetailPage(token: detail)));
  }

  double _livePrice(HotCoin coin) =>
      _livePrices[coin.address.toLowerCase()]?.priceUsd ?? coin.priceUsd;

  double _liveChange24h(HotCoin coin) =>
      _livePrices[coin.address.toLowerCase()]?.priceChange24h ?? coin.priceChange24h;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final topPadding = MediaQuery.of(context).padding.top;

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          // ── 毛玻璃 AppBar ──────────────────
          SliverAppBar(
            pinned: true,
            expandedHeight: topPadding + 52,
            backgroundColor: Colors.transparent,
            surfaceTintColor: Colors.transparent,
            flexibleSpace: ClipRect(
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
                child: Container(
                  color: c.bg.withValues(alpha: 0.7),
                  padding: EdgeInsets.only(top: topPadding + 8, left: 20, bottom: 8),
                  alignment: Alignment.bottomLeft,
                  child: Text(
                    '行情',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w600,
                      color: c.textPrimary,
                      letterSpacing: -0.3,
                    ),
                  ),
                ),
              ),
            ),
          ),

          // ── 毛玻璃分段控制 ────────────────
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 2, 16, 6),
              child: _GlassSegment(
                selected: _segment,
                items: const ['热币', '聪明钱', '新币'],
                onChanged: (v) {
                  HapticFeedback.selectionClick();
                  setState(() => _segment = v);
                },
              ),
            ),
          ),

          // ── 链过滤器（热币 & 聪明钱共用）────
          if (_segment == 0 || _segment == 1)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: List.generate(
                      _segment == 0 ? _chainKeys.length : _smartChainKeys.length,
                      (i) {
                        final isSmartTab = _segment == 1;
                        final selected = isSmartTab ? _smartChainIndex == i : _chainIndex == i;
                        final chainKey = isSmartTab ? _smartChainKeys[i] : _chainKeys[i];
                        final label = i == 0 ? '全部' : (isSmartTab
                            ? switch (chainKey) { 'solana' => 'SOL', 'eth' => 'ETH', 'bsc' => 'BSC', 'base' => 'BASE', _ => '' }
                            : chainKey!);
                        final count = isSmartTab ? _smartChainCount(chainKey as String?) : _chainCount(chainKey as String?);
                        return Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: GestureDetector(
                            onTap: () {
                              HapticFeedback.selectionClick();
                              setState(() {
                                if (isSmartTab) {
                                  _smartChainIndex = i;
                                  _applySmartChainFilter();
                                } else {
                                  _chainIndex = i;
                                  _applyChainFilter();
                                }
                              });
                            },
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 200),
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                              decoration: BoxDecoration(
                                color: selected ? c.primary : c.cardGlass,
                                borderRadius: BorderRadius.circular(10),
                                border: selected ? null : Border.all(color: c.glassBorder),
                                boxShadow: selected ? [
                                  BoxShadow(
                                    color: c.primary.withValues(alpha: 0.25),
                                    blurRadius: 8,
                                    offset: const Offset(0, 2),
                                  ),
                                ] : null,
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(label, style: TextStyle(
                                    fontSize: 13, fontWeight: FontWeight.w600,
                                    color: selected ? Colors.white : c.textSecondary,
                                  )),
                                  if (count > 0) ...[
                                    const SizedBox(width: 4),
                                    Text('$count', style: TextStyle(
                                      fontSize: 11, fontWeight: FontWeight.w500,
                                      color: selected
                                          ? Colors.white.withValues(alpha: 0.7)
                                          : c.textTertiary,
                                    )),
                                  ],
                                ],
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ),
              ),
            ),

          // ── 新币日期 ──────────────────────
          if (_segment == 2)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
                child: Row(
                  children: [
                    Text(DateFormat('M月d日').format(DateTime.now()),
                      style: TextStyle(color: c.textSecondary, fontSize: 14)),
                    const Spacer(),
                    if (_picks.isNotEmpty)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: c.success.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: c.success.withValues(alpha: 0.2)),
                        ),
                        child: Text(
                          '${_picks.where((p) => p.recommendation == "strong").length} 强推',
                          style: TextStyle(color: c.success, fontSize: 12, fontWeight: FontWeight.w700),
                        ),
                      ),
                  ],
                ),
              ),
            ),

          CupertinoSliverRefreshControl(
            onRefresh: () {
              if (_segment == 0) return _loadHot();
              if (_segment == 1) return _loadSmartMoney();
              return _loadPicks();
            },
          ),
          if (_segment == 0)
            ..._buildHotContent()
          else if (_segment == 1)
            ..._buildSmartMoneyContent()
          else
            ..._buildPicksContent(),

          // 底部留白（给浮动 Tab Bar 留空间）
          const SliverToBoxAdapter(child: SizedBox(height: 100)),
        ],
      ),
    );
  }

  List<Widget> _buildHotContent() {
    final c = context.colors;

    if (_hotLoading) {
      return [
        const SliverToBoxAdapter(
          child: Padding(padding: EdgeInsets.only(top: 8), child: ShimmerList(itemCount: 8)),
        ),
      ];
    }
    if (_hotError != null) return [SliverFillRemaining(child: _ErrorView(onRetry: _loadHot))];
    if (_hotFiltered.isEmpty) return [const SliverFillRemaining(child: _EmptyView(icon: CupertinoIcons.flame, text: '暂无热门代币'))];

    return [
      // ── 列头 ──────────────────────
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
          child: Row(
            children: [
              const SizedBox(width: 34),
              Text('代币', style: TextStyle(fontSize: 11, color: c.textTertiary, fontWeight: FontWeight.w500)),
              const Spacer(),
              Text('价格 / 24h涨跌', style: TextStyle(fontSize: 11, color: c.textTertiary, fontWeight: FontWeight.w500)),
              const SizedBox(width: 14),
            ],
          ),
        ),
      ),
      // ── 玻璃列表容器 ──────────────
      SliverToBoxAdapter(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: c.cardGlass,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: c.glassBorder, width: 0.5),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: Column(
              children: List.generate(_hotFiltered.length, (i) {
                final coin = _hotFiltered[i];
                return Column(children: [
                  HotCoinCard(
                    coin: coin, rank: i + 1,
                    livePrice: _livePrice(coin),
                    liveChange24h: _liveChange24h(coin),
                    onTap: () => _openHotDetail(coin),
                  ),
                  if (i < _hotFiltered.length - 1)
                    Padding(
                      padding: const EdgeInsets.only(left: 80),
                      child: Container(height: 0.5, color: c.divider),
                    ),
                ]);
              }),
            ),
          ),
        ),
      ),
      // ── 底部统计 ────────────────────
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          child: Center(
            child: Text(
              '${_hotFiltered.where((c) => c.recommendation == "strong").length} 强推 · ${_hotFiltered.length} 个代币 · 实时',
              style: TextStyle(fontSize: 12, color: c.textTertiary),
            ),
          ),
        ),
      ),
    ];
  }

  List<Widget> _buildSmartMoneyContent() {
    final c = context.colors;

    if (_smartLoading) {
      return [
        const SliverToBoxAdapter(
          child: Padding(padding: EdgeInsets.only(top: 8), child: ShimmerList(itemCount: 8)),
        ),
      ];
    }
    if (_smartError != null) return [SliverFillRemaining(child: _ErrorView(onRetry: _loadSmartMoney))];
    if (_smartFiltered.isEmpty) return [const SliverFillRemaining(child: _EmptyView(icon: CupertinoIcons.money_dollar_circle, text: '暂无聪明钱信号'))];

    return [
      // ── 列头 ──────────────────
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
          child: Row(
            children: [
              const SizedBox(width: 34),
              Text('代币', style: TextStyle(fontSize: 11, color: c.textTertiary, fontWeight: FontWeight.w500)),
              const Spacer(),
              Text('价格 / 热度', style: TextStyle(fontSize: 11, color: c.textTertiary, fontWeight: FontWeight.w500)),
              const SizedBox(width: 14),
            ],
          ),
        ),
      ),
      // ── 玻璃列表容器 ──────────
      SliverToBoxAdapter(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: c.cardGlass,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: c.glassBorder, width: 0.5),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: Column(
              children: List.generate(_smartFiltered.length, (i) {
                final sig = _smartFiltered[i];
                return Column(children: [
                  SmartMoneyCard(
                    signal: sig, rank: i + 1,
                    onTap: () => _openSmartMoneyDetail(sig),
                  ),
                  if (i < _smartFiltered.length - 1)
                    Padding(
                      padding: const EdgeInsets.only(left: 80),
                      child: Container(height: 0.5, color: c.divider),
                    ),
                ]);
              }),
            ),
          ),
        ),
      ),
      // ── 底部统计 ──────────────
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          child: Center(
            child: Text(
              '${_smartFiltered.where((s) => s.signalStrength == "strong").length} 强信号 · ${_smartFiltered.length} 个代币 · 每5分钟更新',
              style: TextStyle(fontSize: 12, color: c.textTertiary),
            ),
          ),
        ),
      ),
    ];
  }

  List<Widget> _buildPicksContent() {
    final c = context.colors;

    if (_picksLoading) {
      return [
        const SliverToBoxAdapter(
          child: Padding(padding: EdgeInsets.only(top: 8), child: ShimmerList(itemCount: 6)),
        ),
      ];
    }
    if (_picksError != null) return [SliverFillRemaining(child: _ErrorView(onRetry: _loadPicks))];
    if (_picks.isEmpty) return [const SliverFillRemaining(child: _EmptyView(icon: CupertinoIcons.bolt, text: '今日信号尚未生成'))];

    return [
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
          child: Row(
            children: [
              const SizedBox(width: 34),
              Text('代币', style: TextStyle(fontSize: 11, color: c.textTertiary, fontWeight: FontWeight.w500)),
              const Spacer(),
              Text('评分', style: TextStyle(fontSize: 11, color: c.textTertiary, fontWeight: FontWeight.w500)),
              const SizedBox(width: 22),
            ],
          ),
        ),
      ),
      SliverToBoxAdapter(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: c.cardGlass,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: c.glassBorder, width: 0.5),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: Column(
              children: List.generate(_picks.length, (i) {
                final pick = _picks[i];
                return Column(children: [
                  PickCard(pick: pick, onTap: () => _openPickDetail(pick)),
                  if (i < _picks.length - 1)
                    Padding(
                      padding: const EdgeInsets.only(left: 80),
                      child: Container(height: 0.5, color: c.divider),
                    ),
                ]);
              }),
            ),
          ),
        ),
      ),
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          child: Center(
            child: Text(
              '每日 UTC 00:05 更新 · pump.fun 内盘扫描',
              textAlign: TextAlign.center,
              style: TextStyle(color: c.textTertiary, fontSize: 12),
            ),
          ),
        ),
      ),
    ];
  }
}

// ═══════════════════════════════════════════════════════════
//  玻璃分段控制器
// ═══════════════════════════════════════════════════════════
class _GlassSegment extends StatelessWidget {
  final int selected;
  final List<String> items;
  final ValueChanged<int> onChanged;

  const _GlassSegment({
    required this.selected,
    required this.items,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      height: 34,
      decoration: BoxDecoration(
        color: c.cardGlass,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: c.glassBorder, width: 0.5),
      ),
      child: Row(
        children: List.generate(items.length, (i) {
          final isActive = i == selected;
          return Expanded(
            child: GestureDetector(
              onTap: () => onChanged(i),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                curve: Curves.easeOutCubic,
                margin: const EdgeInsets.all(2.5),
                decoration: BoxDecoration(
                  color: isActive ? c.surface : Colors.transparent,
                  borderRadius: BorderRadius.circular(6),
                  boxShadow: isActive ? [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.08),
                      blurRadius: 4,
                      offset: const Offset(0, 1),
                    ),
                  ] : null,
                ),
                alignment: Alignment.center,
                child: Text(
                  items[i],
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
                    color: isActive ? c.textPrimary : c.textSecondary,
                  ),
                ),
              ),
            ),
          );
        }),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════
//  空状态 & 错误状态
// ═══════════════════════════════════════════════════════════
class _EmptyView extends StatelessWidget {
  final IconData icon;
  final String text;
  const _EmptyView({required this.icon, required this.text});
  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 48, color: c.textTertiary),
      const SizedBox(height: 14),
      Text(text, style: TextStyle(color: c.textPrimary, fontSize: 17, fontWeight: FontWeight.w600)),
      const SizedBox(height: 8),
      Text('下拉刷新试试', style: TextStyle(color: c.textSecondary, fontSize: 15)),
    ]));
  }
}

class _ErrorView extends StatelessWidget {
  final VoidCallback onRetry;
  const _ErrorView({required this.onRetry});
  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(CupertinoIcons.wifi_slash, size: 48, color: c.textTertiary),
      const SizedBox(height: 14),
      Text('加载失败', style: TextStyle(color: c.textPrimary, fontSize: 17, fontWeight: FontWeight.w600)),
      const SizedBox(height: 16),
      CupertinoButton(
        onPressed: onRetry,
        child: Text('重试', style: TextStyle(fontWeight: FontWeight.w600, color: c.primary)),
      ),
    ]));
  }
}
