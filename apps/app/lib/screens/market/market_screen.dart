import 'dart:async';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/hot_coin.dart';
import '../../models/daily_pick.dart';
import '../../models/token_detail.dart';
import '../../services/supabase_service.dart';
import '../../services/price_ticker_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/hot_coin_card.dart';
import '../../widgets/pick_card.dart';
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
  static const _chainKeys = [null, 'SOL', 'BSC', 'BASE'];

  // 实时价格覆盖
  Map<String, PriceTick> _livePrices = {};
  StreamSubscription? _priceSub;

  List<DailyPick> _picks = [];
  bool _picksLoading = true;
  String? _picksError;

  @override
  void initState() {
    super.initState();
    _loadHot();
    _loadPicks();
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

  void _openHotDetail(HotCoin coin) {
    Navigator.push(context,
      CupertinoPageRoute(builder: (_) => TokenDetailPage(token: TokenDetail.fromHotCoin(coin))));
  }

  void _openPickDetail(DailyPick pick) {
    Navigator.push(context,
      CupertinoPageRoute(builder: (_) => TokenDetailPage(token: TokenDetail.fromDailyPick(pick))));
  }

  double _livePrice(HotCoin coin) =>
      _livePrices[coin.address.toLowerCase()]?.priceUsd ?? coin.priceUsd;

  double _liveChange24h(HotCoin coin) =>
      _livePrices[coin.address.toLowerCase()]?.priceChange24h ?? coin.priceChange24h;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          CupertinoSliverNavigationBar(
            largeTitle: const Text('行情'),
            backgroundColor: AppColors.bg.withValues(alpha: 0.9),
            border: null,
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
              child: CupertinoSlidingSegmentedControl<int>(
                groupValue: _segment,
                onValueChanged: (v) { if (v != null) setState(() => _segment = v); },
                children: const {
                  0: Padding(padding: EdgeInsets.symmetric(horizontal: 12),
                    child: Text('热币', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500))),
                  1: Padding(padding: EdgeInsets.symmetric(horizontal: 12),
                    child: Text('新币', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w500))),
                },
              ),
            ),
          ),
          if (_segment == 0)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: Row(
                  children: List.generate(_chainKeys.length, (i) {
                    final selected = _chainIndex == i;
                    final label = i == 0 ? '全部' : _chainKeys[i]!;
                    return Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: GestureDetector(
                        onTap: () => setState(() { _chainIndex = i; _applyChainFilter(); }),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: selected ? AppColors.primary : AppColors.surface,
                            borderRadius: BorderRadius.circular(8),
                            border: selected ? null : Border.all(color: AppColors.divider.withValues(alpha: 0.3)),
                          ),
                          child: Text(label, style: TextStyle(
                            fontSize: 13, fontWeight: FontWeight.w500,
                            color: selected ? Colors.white : AppColors.textSecondary,
                          )),
                        ),
                      ),
                    );
                  }),
                ),
              ),
            ),
          if (_segment == 1)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: Row(
                  children: [
                    Text(DateFormat('M月d日').format(DateTime.now()),
                      style: const TextStyle(color: AppColors.textSecondary, fontSize: 14)),
                    const Spacer(),
                    if (_picks.isNotEmpty)
                      Text('${_picks.where((p) => p.recommendation == "strong").length} 强推',
                        style: const TextStyle(color: AppColors.strong, fontSize: 13, fontWeight: FontWeight.w600)),
                  ],
                ),
              ),
            ),
          CupertinoSliverRefreshControl(
            onRefresh: () => _segment == 0 ? _loadHot() : _loadPicks(),
          ),
          if (_segment == 0) ..._buildHotContent() else ..._buildPicksContent(),
        ],
      ),
    );
  }

  List<Widget> _buildHotContent() {
    if (_hotLoading) return [const SliverFillRemaining(child: Center(child: CupertinoActivityIndicator(radius: 14)))];
    if (_hotError != null) return [SliverFillRemaining(child: _ErrorView(onRetry: _loadHot))];
    if (_hotFiltered.isEmpty) return [const SliverFillRemaining(child: _EmptyView(icon: CupertinoIcons.flame, text: '暂无热门代币'))];

    return [
      SliverToBoxAdapter(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            boxShadow: const [BoxShadow(color: Color(0x08000000), blurRadius: 8, offset: Offset(0, 2))],
          ),
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
                  const Padding(padding: EdgeInsets.only(left: 64),
                    child: Divider(height: 0.5, thickness: 0.5, color: Color(0xFFE5E5EA))),
              ]);
            }),
          ),
        ),
      ),
      SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
          child: Text(
            '${_hotFiltered.where((c) => c.recommendation == "strong").length} 强推 · '
            '${_hotFiltered.length} 个 · 实时价格',
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
          ),
        ),
      ),
    ];
  }

  List<Widget> _buildPicksContent() {
    if (_picksLoading) return [const SliverFillRemaining(child: Center(child: CupertinoActivityIndicator(radius: 14)))];
    if (_picksError != null) return [SliverFillRemaining(child: _ErrorView(onRetry: _loadPicks))];
    if (_picks.isEmpty) return [const SliverFillRemaining(child: _EmptyView(icon: CupertinoIcons.bolt, text: '今日信号尚未生成'))];

    return [
      SliverToBoxAdapter(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            boxShadow: const [BoxShadow(color: Color(0x08000000), blurRadius: 8, offset: Offset(0, 2))],
          ),
          child: Column(
            children: List.generate(_picks.length, (i) {
              final pick = _picks[i];
              return Column(children: [
                PickCard(pick: pick, onTap: () => _openPickDetail(pick)),
                if (i < _picks.length - 1)
                  const Padding(padding: EdgeInsets.only(left: 64),
                    child: Divider(height: 0.5, thickness: 0.5, color: Color(0xFFE5E5EA))),
              ]);
            }),
          ),
        ),
      ),
      const SliverToBoxAdapter(
        child: Padding(
          padding: EdgeInsets.fromLTRB(16, 16, 16, 32),
          child: Text('每日 UTC 00:05 更新 · pump.fun 内盘扫描',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
        ),
      ),
    ];
  }
}

class _EmptyView extends StatelessWidget {
  final IconData icon;
  final String text;
  const _EmptyView({required this.icon, required this.text});
  @override
  Widget build(BuildContext context) {
    return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 44, color: AppColors.textTertiary),
      const SizedBox(height: 12),
      Text(text, style: const TextStyle(color: AppColors.textPrimary, fontSize: 17, fontWeight: FontWeight.w600)),
      const SizedBox(height: 6),
      const Text('下拉刷新试试', style: TextStyle(color: AppColors.textSecondary, fontSize: 15)),
    ]));
  }
}

class _ErrorView extends StatelessWidget {
  final VoidCallback onRetry;
  const _ErrorView({required this.onRetry});
  @override
  Widget build(BuildContext context) {
    return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(CupertinoIcons.wifi_slash, size: 44, color: AppColors.textTertiary),
      const SizedBox(height: 12),
      const Text('加载失败', style: TextStyle(color: AppColors.textPrimary, fontSize: 17, fontWeight: FontWeight.w600)),
      const SizedBox(height: 16),
      CupertinoButton(onPressed: onRetry, child: const Text('重试')),
    ]));
  }
}
