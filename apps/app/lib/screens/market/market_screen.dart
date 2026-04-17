import 'dart:async';
import 'dart:ui';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import '../../models/hot_coin.dart';
import '../../models/pump_signal.dart';
import '../../models/smart_money_signal.dart';
import '../../models/token_detail.dart';
import '../../services/supabase_service.dart';
import '../../services/pump_signal_service.dart';
import '../../services/price_ticker_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/common/token_avatar.dart';
import '../../widgets/hot_coin_card.dart';
import '../../widgets/smart_money_card.dart';
import '../../widgets/smart_money_detail_sheet.dart';
import '../../widgets/shimmer_list.dart';
import '../../l10n/app_localizations.dart';
import '../detail/token_detail_page.dart';
import '../btc_eth/btc_eth_page.dart';

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

  List<PumpSignal> _picks = [];
  bool _picksLoading = true;
  String? _picksError;
  Timer? _picksTimer;

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
    _picksTimer = Timer.periodic(const Duration(seconds: 30), (_) => _loadPicks());
    _priceSub = PriceTickerService.instance.stream.listen((prices) {
      if (mounted) setState(() => _livePrices = prices);
    });
  }

  @override
  void dispose() {
    _priceSub?.cancel();
    _picksTimer?.cancel();
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
        // 按链分组地址，启用多链实时价格
        final chainAddrs = <String, List<String>>{};
        for (final coin in coins) {
          final chain = coin.chain.isNotEmpty ? coin.chain : 'solana';
          chainAddrs.putIfAbsent(chain, () => []).add(coin.address);
        }
        PriceTickerService.instance.startMultiChain(chainAddrs);
      }
    } catch (e) {
      if (mounted) setState(() { _hotError = e.toString(); _hotLoading = false; });
    }
  }

  Future<void> _loadPicks() async {
    try {
      final result = await PumpSignalService.instance.fetchSignals();
      if (mounted) setState(() { _picks = result.signals; _picksLoading = false; _picksError = null; });
    } catch (e) {
      if (mounted && _picks.isEmpty) setState(() { _picksError = e.toString(); _picksLoading = false; });
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

  void _openPickDetail(PumpSignal signal) {
    Navigator.push(context,
      CupertinoPageRoute(builder: (_) => TokenDetailPage(token: _signalToDetail(signal))));
  }

  TokenDetail _signalToDetail(PumpSignal s) {
    return TokenDetail(
      chain: 'solana', address: s.mint, name: s.name, symbol: s.symbol,
      priceUsd: 0, marketCapUsd: 0, liquidityUsd: 0,
      volume24hUsd: 0, volume1hUsd: 0,
      priceChange1h: 0, priceChange6h: 0, priceChange24h: 0,
      buys1h: 0, sells1h: 0, buys24h: 0, sells24h: 0,
      ageDays: s.ageMinutes / 1440, holderCount: 0,
      goplusRisk: false,
      hasTwitter: s.twitter != null, hasTelegram: s.telegram != null, hasWebsite: s.website != null,
      score: s.score, scoreDetail: s.scoreDetail, recommendation: s.recommendation,
      source: TokenSource.pumpSignal, bcProgress: s.bcProgress, imageUri: s.imageUri,
    );
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
    showSmartMoneyDetailSheet(context, sig);
  }

  double _livePrice(HotCoin coin) =>
      _livePrices[coin.address.toLowerCase()]?.priceUsd ?? coin.priceUsd;

  double _liveChange24h(HotCoin coin) =>
      _livePrices[coin.address.toLowerCase()]?.priceChange24h ?? coin.priceChange24h;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final t = S.of(context);
    final topPadding = MediaQuery.of(context).padding.top;

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          // ── 标题（直接吸顶）──────────────────
          SliverToBoxAdapter(
            child: Padding(
              padding: EdgeInsets.only(top: topPadding + 8, left: 20, bottom: 4),
              child: Text(
                t.marketTitle,
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  color: c.textPrimary,
                  letterSpacing: -0.3,
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
                items: [t.hotCoins, t.smartMoney, t.newCoins, 'BTC/ETH'],
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
                        final label = i == 0 ? t.all : (isSmartTab
                            ? switch (chainKey) { 'solana' => 'SOL', 'eth' => 'ETH', 'bsc' => 'BSC', 'base' => 'BASE', _ => '' }
                            : chainKey!);
                        final count = isSmartTab ? _smartChainCount(chainKey) : _chainCount(chainKey);
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
                    Text(DateFormat.MMMd(Localizations.localeOf(context).languageCode).format(DateTime.now()),
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
                          t.strongPushWithCount(_picks.where((p) => p.recommendation == "strong").length),
                          style: TextStyle(color: c.success, fontSize: 12, fontWeight: FontWeight.w700),
                        ),
                      ),
                  ],
                ),
              ),
            ),

          if (_segment != 3)  // BTC/ETH 有自己的刷新机制
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
          else if (_segment == 2)
            ..._buildPicksContent()
          else
            ..._buildBtcEthContent(),

          // 底部留白（给浮动 Tab Bar 留空间）
          const SliverToBoxAdapter(child: SizedBox(height: 100)),
        ],
      ),
    );
  }

  List<Widget> _buildHotContent() {
    final c = context.colors;
    final t = S.of(context);

    if (_hotLoading) {
      return [
        const SliverToBoxAdapter(
          child: Padding(padding: EdgeInsets.only(top: 8), child: ShimmerList(itemCount: 8)),
        ),
      ];
    }
    if (_hotError != null) return [SliverFillRemaining(child: _ErrorView(onRetry: _loadHot))];
    if (_hotFiltered.isEmpty) return [SliverFillRemaining(child: _EmptyView(icon: CupertinoIcons.flame, text: t.noHotCoins))];

    return [
      // ── 列头 ──────────────────────
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
          child: Row(
            children: [
              const SizedBox(width: 34),
              Text(t.token, style: TextStyle(fontSize: 11, color: c.textTertiary, fontWeight: FontWeight.w500)),
              const Spacer(),
              Text(t.priceChange24hLabel, style: TextStyle(fontSize: 11, color: c.textTertiary, fontWeight: FontWeight.w500)),
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
              t.tokenCountRealtime(_hotFiltered.where((c) => c.recommendation == "strong").length, _hotFiltered.length),
              style: TextStyle(fontSize: 12, color: c.textTertiary),
            ),
          ),
        ),
      ),
    ];
  }

  List<Widget> _buildSmartMoneyContent() {
    final c = context.colors;
    final t = S.of(context);

    if (_smartLoading) {
      return [
        const SliverToBoxAdapter(
          child: Padding(padding: EdgeInsets.only(top: 8), child: ShimmerList(itemCount: 8)),
        ),
      ];
    }
    if (_smartError != null) return [SliverFillRemaining(child: _ErrorView(onRetry: _loadSmartMoney))];
    if (_smartFiltered.isEmpty) return [SliverFillRemaining(child: _EmptyView(icon: CupertinoIcons.money_dollar_circle, text: t.noSmartMoneySignals))];

    return [
      // ── 列头 ──────────────────
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
          child: Row(
            children: [
              const SizedBox(width: 34),
              Text(t.token, style: TextStyle(fontSize: 11, color: c.textTertiary, fontWeight: FontWeight.w500)),
              const Spacer(),
              Text(t.priceHeatLabel, style: TextStyle(fontSize: 11, color: c.textTertiary, fontWeight: FontWeight.w500)),
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
              t.strongSignalInfo(_smartFiltered.where((s) => s.signalStrength == "strong").length, _smartFiltered.length),
              style: TextStyle(fontSize: 12, color: c.textTertiary),
            ),
          ),
        ),
      ),
    ];
  }

  List<Widget> _buildPicksContent() {
    final c = context.colors;
    final t = S.of(context);

    if (_picksLoading) {
      return [
        const SliverToBoxAdapter(
          child: Padding(padding: EdgeInsets.only(top: 8), child: ShimmerList(itemCount: 6)),
        ),
      ];
    }
    if (_picksError != null) return [SliverFillRemaining(child: _ErrorView(onRetry: _loadPicks))];
    if (_picks.isEmpty) return [SliverFillRemaining(child: _EmptyView(icon: CupertinoIcons.waveform, text: t.noSignals))];

    return [
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
          child: Row(
            children: [
              const SizedBox(width: 34),
              Text(t.token, style: TextStyle(fontSize: 11, color: c.textTertiary, fontWeight: FontWeight.w500)),
              const Spacer(),
              Text(t.scoreLabel, style: TextStyle(fontSize: 11, color: c.textTertiary, fontWeight: FontWeight.w500)),
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
                final signal = _picks[i];
                return Column(children: [
                  _PumpSignalRow(signal: signal, rank: i + 1, onTap: () => _openPickDetail(signal)),
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
              t.scanInfo,
              textAlign: TextAlign.center,
              style: TextStyle(color: c.textTertiary, fontSize: 12),
            ),
          ),
        ),
      ),
    ];
  }

  List<Widget> _buildBtcEthContent() {
    return [
      SliverFillRemaining(
        hasScrollBody: true,
        child: const BtcEthPage(),
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
      Text(S.of(context).pullToRefresh, style: TextStyle(color: c.textSecondary, fontSize: 15)),
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
      Text(S.of(context).loadFailed, style: TextStyle(color: c.textPrimary, fontSize: 17, fontWeight: FontWeight.w600)),
      const SizedBox(height: 16),
      CupertinoButton(
        onPressed: onRetry,
        child: Text(S.of(context).retry, style: TextStyle(fontWeight: FontWeight.w600, color: c.primary)),
      ),
    ]));
  }
}

// ═══════════════════════════════════════════════════════════
//  实时信号行（替代 PickCard）
// ═══════════════════════════════════════════════════════════
class _PumpSignalRow extends StatelessWidget {
  final PumpSignal signal;
  final int rank;
  final VoidCallback? onTap;

  const _PumpSignalRow({required this.signal, required this.rank, this.onTap});

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final isStrong = signal.isStrong;

    return CupertinoButton(
      padding: EdgeInsets.zero,
      onPressed: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
        child: Row(
          children: [
            SizedBox(
              width: 24,
              child: Text(
                '$rank',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: rank <= 3 ? c.primary : c.textSecondary,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ),
            const SizedBox(width: 8),
            TokenAvatar(imageUrl: signal.imageUri, symbol: signal.symbol, chain: 'solana', size: 38),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(children: [
                    Flexible(
                      child: Text(
                        signal.symbol.toUpperCase(),
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: c.textPrimary, letterSpacing: -0.3),
                      ),
                    ),
                    if (isStrong) ...[
                      const SizedBox(width: 5),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                        decoration: BoxDecoration(gradient: c.successGradient, borderRadius: BorderRadius.circular(4)),
                        child: Text(S.of(context).strongPush, style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w800)),
                      ),
                    ],
                  ]),
                  const SizedBox(height: 5),
                  Row(children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                      decoration: BoxDecoration(
                        color: c.primary.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        'BC ${signal.bcProgress.toStringAsFixed(1)}%',
                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: c.primary),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(S.of(context).buyersCount(signal.uniqueBuyers), style: TextStyle(fontSize: 11, color: c.textSecondary)),
                    const SizedBox(width: 6),
                    Text(signal.ageLabel, style: TextStyle(fontSize: 11, color: c.textTertiary)),
                  ]),
                ],
              ),
            ),
            Container(
              constraints: const BoxConstraints(minWidth: 38),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              decoration: BoxDecoration(
                gradient: signal.score >= 75 ? c.successGradient : c.primaryGradient,
                borderRadius: BorderRadius.circular(6),
              ),
              alignment: Alignment.center,
              child: Text(
                signal.score.toStringAsFixed(0),
                style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w800, fontFeatures: [FontFeature.tabularFigures()]),
              ),
            ),
            const SizedBox(width: 4),
            Icon(CupertinoIcons.chevron_right, size: 12, color: c.textTertiary),
          ],
        ),
      ),
    );
  }
}
