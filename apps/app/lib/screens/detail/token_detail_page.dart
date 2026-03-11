import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../models/token_detail.dart';
import '../../models/ohlcv_data.dart';
import '../../models/goplus_report.dart';
import '../../models/dexscreener_info.dart';
import '../../services/token_detail_service.dart';
import '../../services/gecko_terminal_service.dart';
import '../../services/coingecko_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/detail/tradingview_chart.dart';
import '../../widgets/detail/recent_trades_card.dart';
import '../../widgets/detail/holder_info_card.dart';
import '../../widgets/detail/security_check_card.dart';
import '../../widgets/detail/shimmer_skeleton.dart';

class TokenDetailPage extends StatefulWidget {
  final TokenDetail token;
  const TokenDetailPage({super.key, required this.token});

  @override
  State<TokenDetailPage> createState() => _TokenDetailPageState();
}

class _TokenDetailPageState extends State<TokenDetailPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  GoPlusReport? _goplus;
  DexScreenerInfo? _dexInfo;
  CoinGeckoTokenInfo? _coinGecko;
  double? _top1Pct;
  String? _resolvedPair;

  List<OhlcvCandle> _candles = [];
  String _timeframe = '1h';
  bool _candleLoading = true;
  final Map<String, List<OhlcvCandle>> _candleCache = {};

  bool _enrichLoading = true;
  bool _goplusLoading = true;

  // ── Bitget: 指标 + 子Tab + 动态筛选 ──
  Set<String> _activeIndicators = {'VOL', 'MA'};
  int _subTabIndex = 0;
  String _dynamicsTf = '1h';
  String _detailDynTf = '1h'; // 详情Tab交易动态的时间筛选

  // ── 用于控制行情Tab专属header的显示 ──
  int _mainTabIndex = 0;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    // 监听主Tab切换，控制行情专属header区域的显示/隐藏
    _tabController.addListener(() {
      if (_tabController.index != _mainTabIndex) {
        setState(() => _mainTabIndex = _tabController.index);
      }
    });
    _loadEnrichment();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadEnrichment() async {
    try {
      final result = await TokenDetailService.instance.loadEnrichment(
        chain: widget.token.chain,
        address: widget.token.address,
        pairAddress: widget.token.pairAddress,
      );
      if (!mounted) return;
      setState(() {
        _goplus = result.goplusReport;
        _dexInfo = result.dexScreenerInfo;
        _coinGecko = result.coinGeckoInfo;
        _top1Pct = result.top1HolderPct;
        _resolvedPair = result.resolvedPairAddress;
        _candles = result.initialCandles;
        _candleCache['1h'] = result.initialCandles;
        _enrichLoading = false;
        _goplusLoading = false;
        _candleLoading = false;
      });
    } catch (_) {
      if (mounted) {
        setState(() {
          _enrichLoading = false;
          _goplusLoading = false;
          _candleLoading = false;
        });
      }
    }
  }

  Future<void> _switchTimeframe(String tf) async {
    if (tf == _timeframe) return;
    setState(() { _timeframe = tf; _candleLoading = true; });

    if (_candleCache.containsKey(tf)) {
      setState(() { _candles = _candleCache[tf]!; _candleLoading = false; });
      return;
    }

    final pair = _resolvedPair ?? widget.token.pairAddress;
    if (pair == null || pair.isEmpty) {
      setState(() { _candles = []; _candleLoading = false; });
      return;
    }

    final (timeframe, aggregate) = _tfParams(tf);
    try {
      final data = await GeckoTerminalService.instance.fetchOhlcv(
        network: widget.token.geckoNetwork,
        poolAddress: pair,
        timeframe: timeframe,
        aggregate: aggregate,
        limit: 100,
      );
      if (mounted) {
        _candleCache[tf] = data;
        setState(() { _candles = data; _candleLoading = false; });
      }
    } catch (_) {
      if (mounted) setState(() { _candleLoading = false; });
    }
  }

  (String, int) _tfParams(String tf) => switch (tf) {
    '5m' => ('minute', 5),
    '15m' => ('minute', 15),
    '1h' => ('hour', 1),
    '4h' => ('hour', 4),
    '1d' => ('day', 1),
    _ => ('hour', 1),
  };

  void _copyAddress() {
    Clipboard.setData(ClipboardData(text: widget.token.address));
    final overlay = Overlay.of(context);
    final entry = OverlayEntry(
      builder: (_) => Positioned(
        bottom: 100, left: 0, right: 0,
        child: Center(child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(color: Colors.black87, borderRadius: BorderRadius.circular(8)),
          child: const Text('已复制', style: TextStyle(color: Colors.white, fontSize: 14)),
        )),
      ),
    );
    overlay.insert(entry);
    Future.delayed(const Duration(seconds: 1), () => entry.remove());
  }

  // ════════════════════════════════════════════════
  //  BUILD
  // ════════════════════════════════════════════════
  @override
  Widget build(BuildContext context) {
    final token = widget.token;
    final shortAddr = '${token.address.substring(0, 6)}...${token.address.substring(token.address.length - 4)}';
    final imageUrl = _dexInfo?.imageUrl ?? token.imageUri;

    return Scaffold(
      backgroundColor: context.colors.bg,
      body: NestedScrollView(
        headerSliverBuilder: (context, _) => [
          // ── AppBar + 主 Tab ──
          SliverAppBar(
            pinned: true,
            backgroundColor: context.colors.bg,
            elevation: 0,
            scrolledUnderElevation: 0,
            surfaceTintColor: Colors.transparent,
            leading: IconButton(
              icon: const Icon(CupertinoIcons.back, size: 22),
              color: context.colors.textPrimary,
              onPressed: () => Navigator.of(context).pop(),
            ),
            title: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (imageUrl != null && imageUrl.isNotEmpty)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(14),
                    child: Image.network(imageUrl, width: 28, height: 28, fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => _miniAvatar(token)),
                  )
                else
                  _miniAvatar(token),
                const SizedBox(width: 8),
                Flexible(
                  child: Text(token.symbol.toUpperCase(),
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 18, color: context.colors.textPrimary),
                    overflow: TextOverflow.ellipsis),
                ),
                const SizedBox(width: 4),
                Icon(CupertinoIcons.chevron_down, size: 14, color: context.colors.textSecondary),
              ],
            ),
            actions: [
              GestureDetector(
                onTap: _copyAddress,
                child: Padding(
                  padding: const EdgeInsets.only(right: 4),
                  child: DecoratedBox(
                    decoration: BoxDecoration(color: context.colors.bg, borderRadius: BorderRadius.circular(6)),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                      child: Row(mainAxisSize: MainAxisSize.min, children: [
                        Text(shortAddr, style: TextStyle(fontSize: 11, color: context.colors.textSecondary, fontFamily: 'Menlo')),
                        const SizedBox(width: 2),
                        Icon(CupertinoIcons.doc_on_clipboard, size: 11, color: context.colors.textTertiary),
                      ]),
                    ),
                  ),
                ),
              ),
              if (token.ageDays > 0)
                Padding(
                  padding: const EdgeInsets.only(right: 4),
                  child: DecoratedBox(
                    decoration: BoxDecoration(color: context.colors.bg, borderRadius: BorderRadius.circular(6)),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                      child: Text('${token.ageDays.toStringAsFixed(0)}天',
                        style: TextStyle(fontSize: 11, color: context.colors.textSecondary)),
                    ),
                  ),
                ),
              const SizedBox(width: 8),
            ],
            bottom: TabBar(
              controller: _tabController,
              labelColor: context.colors.textPrimary,
              unselectedLabelColor: context.colors.textSecondary,
              labelStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
              unselectedLabelStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w400),
              indicatorColor: context.colors.textPrimary,
              indicatorWeight: 2.5,
              indicatorSize: TabBarIndicatorSize.label,
              dividerColor: Colors.transparent,
              splashFactory: NoSplash.splashFactory,
              overlayColor: WidgetStateProperty.all(Colors.transparent),
              tabs: const [Tab(text: '行情'), Tab(text: '详情'), Tab(text: '安全检测')],
            ),
          ),
          // ── 价格区域（Bitget 左右布局）──
          SliverToBoxAdapter(child: _buildPriceHeader(token)),

          // ── 行情Tab专属：K线图 + 指标选择器 + 子Tab吸顶 ──
          // 放在 headerSliverBuilder 中才能让子Tab正确吸顶
          if (_mainTabIndex == 0 && !_enrichLoading) ...[
            SliverToBoxAdapter(child: _buildTimeframeSelector()),
            SliverToBoxAdapter(
              child: TradingViewChart(
                candles: _candles,
                selectedTimeframe: _timeframe,
                onTimeframeChanged: _switchTimeframe,
                loading: _candleLoading,
                showControls: false,
                activeIndicators: _activeIndicators,
              ),
            ),
            SliverToBoxAdapter(child: _buildIndicatorSelector()),
            SliverPersistentHeader(
              pinned: true,
              delegate: _StickyHeaderDelegate(
                child: _buildSubTabBar(),
                height: 46,
              ),
            ),
          ],
        ],
        body: _enrichLoading
          ? const SingleChildScrollView(
              padding: EdgeInsets.only(top: 8, bottom: 40),
              child: ShimmerSkeleton(),
            )
          : TabBarView(
              controller: _tabController,
              children: [
                _buildMarketTab(token),
                _buildDetailTab(token),
                _buildSecurityTab(),
              ],
            ),
      ),
    );
  }

  // ════════════════════════════════════════════════
  //  价格 Header — Bitget 左右布局
  // ════════════════════════════════════════════════
  Widget _buildPriceHeader(TokenDetail token) {
    // DexScreener 实时数据回填：当 token 的静态数据为 0 时使用
    final dexPrice = _dexInfo?.pairs.isNotEmpty == true
        ? _dexInfo!.pairs.first.priceUsd : null;
    final effectivePrice = token.priceUsd > 0 ? token.priceUsd : (dexPrice ?? 0);

    final change24h = token.priceChange24h;
    final isPos = change24h >= 0;
    final changeColor = isPos ? context.colors.success : context.colors.danger;

    return ColoredBox(
      color: context.colors.bg,
      child: Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 左侧：价格 + 涨跌 + 标签 + 社交
          Expanded(
            flex: 5,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(_fmtPrice(effectivePrice), style: TextStyle(
                  fontSize: 26, fontWeight: FontWeight.w800, color: context.colors.textPrimary,
                  letterSpacing: -1, height: 1.1,
                  fontFeatures: const [FontFeature.tabularFigures()],
                )),
                const SizedBox(height: 3),
                Text('${isPos ? "+" : ""}${change24h.toStringAsFixed(2)}%',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: changeColor)),
                const SizedBox(height: 8),
                Row(children: [
                  if (token.recommendation.isNotEmpty) ...[
                    _bitgetTag(token.recommendation, context.colors.success),
                    const SizedBox(width: 6),
                  ],
                  _bitgetTag(token.chainLabel, context.colors.primary),
                  if (token.isDailyPick) ...[const SizedBox(width: 6), _bitgetTag('PumpFun', context.colors.success)],
                ]),
                const SizedBox(height: 8),
                Row(children: [
                  if (token.hasTwitter) ...[
                    Text('𝕏', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: context.colors.textSecondary)),
                    const SizedBox(width: 10),
                  ],
                  if (token.hasWebsite) Icon(CupertinoIcons.globe, size: 15, color: context.colors.textSecondary),
                  if (token.hasTelegram) ...[const SizedBox(width: 10), Icon(CupertinoIcons.paperplane, size: 15, color: context.colors.textSecondary)],
                ]),
              ],
            ),
          ),
          const SizedBox(width: 8),
          // 右侧：5行数据
          Expanded(
            flex: 5,
            child: Column(children: [
              _statRow('市值', _fmtWan(
                token.marketCapUsd > 0 ? token.marketCapUsd
                : (_dexInfo?.marketCap ?? _coinGecko?.marketCap ?? 0)
              )),
              _statRow('资金池', _fmtWan(
                token.liquidityUsd > 0 ? token.liquidityUsd
                : (_dexInfo?.pairs.isNotEmpty == true ? _dexInfo!.pairs.first.liquidity : 0)
              )),
              _statRow('持币地址数', token.holderCount > 0 ? _fmtNum(token.holderCount) : '-'),
              _statRow('Top 10 占比', token.top10HolderPct != null ? '${token.top10HolderPct!.toStringAsFixed(0)}%' : '-'),
              _statRow('24h交易地址数', _fmtNum(token.buys24h + token.sells24h)),
            ]),
          ),
        ],
      ),
    ));
  }

  // ════════════════════════════════════════════════
  //  Tab 1: 行情 — 子Tab内容（图表和子Tab栏已移到headerSliverBuilder实现吸顶）
  // ════════════════════════════════════════════════
  Widget _buildMarketTab(TokenDetail token) {
    return ListView(
      padding: const EdgeInsets.only(bottom: 40),
      children: [
        _buildSubTabContent(token),
      ],
    );
  }

  // ── K线时间选择器 ──
  Widget _buildTimeframeSelector() {
    const tfs = ['5m', '15m', '1h', '4h', '1d'];
    const tfLabels = {'5m': '5分', '15m': '15分', '1h': '1小时', '4h': '4小时', '1d': '1天'};

    return ColoredBox(
      color: context.colors.bg,
      child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: [
          ...tfs.map((tf) {
            final sel = tf == _timeframe;
            return GestureDetector(
              onTap: () => _switchTimeframe(tf),
              child: Container(
                margin: const EdgeInsets.only(right: 2),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: sel ? context.colors.textPrimary : Colors.transparent,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(tfLabels[tf] ?? tf, style: TextStyle(
                  fontSize: 12, fontWeight: sel ? FontWeight.w600 : FontWeight.w400,
                  color: sel ? Colors.white : context.colors.textSecondary,
                )),
              ),
            );
          }),
          const SizedBox(width: 4),
          Text('更多', style: TextStyle(fontSize: 12, color: context.colors.textSecondary)),
          Icon(Icons.arrow_drop_down, size: 16, color: context.colors.textSecondary),
          const Spacer(),
          Text('价格', style: TextStyle(fontSize: 12, color: context.colors.textSecondary)),
          Icon(Icons.arrow_drop_down, size: 16, color: context.colors.textSecondary),
          const SizedBox(width: 8),
          Icon(CupertinoIcons.slider_horizontal_3, size: 16, color: context.colors.textSecondary),
        ],
      ),
    ));
  }

  // ── 指标选择器（点击切换，真正控制图表）──
  Widget _buildIndicatorSelector() {
    const indicators = ['Vol', 'MA', 'BOLL', 'MACD', 'KDJ', 'RSI', 'WR'];

    return ColoredBox(
      color: context.colors.bg,
      child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: indicators.map((ind) {
          final key = ind.toUpperCase();
          final isActive = _activeIndicators.contains(key);
          return GestureDetector(
            onTap: () {
              setState(() {
                if (_activeIndicators.contains(key)) {
                  _activeIndicators = Set.from(_activeIndicators)..remove(key);
                } else {
                  _activeIndicators = Set.from(_activeIndicators)..add(key);
                }
              });
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: isActive ? context.colors.textPrimary.withValues(alpha: 0.08) : Colors.transparent,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(ind, style: TextStyle(
                fontSize: 12,
                color: isActive ? context.colors.textPrimary : context.colors.textSecondary,
                fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
              )),
            ),
          );
        }).toList(),
      ),
    ));
  }

  // ── 子Tab栏（交易动态 | 持币地址 | 资金池 | 开发者代币）──
  Widget _buildSubTabBar() {
    const tabs = ['交易动态', '持币地址', '资金池', '开发者代币'];
    return Container(
      decoration: BoxDecoration(
        color: context.colors.bg,
        border: Border(bottom: BorderSide(color: Color(0xFFE5E5EA), width: 0.5)),
      ),
      child: Row(
        children: List.generate(tabs.length, (i) {
          final sel = i == _subTabIndex;
          return GestureDetector(
            onTap: () => setState(() => _subTabIndex = i),
            child: Container(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 10),
              decoration: BoxDecoration(
                border: Border(bottom: BorderSide(
                  color: sel ? context.colors.primary : Colors.transparent, width: 2.5)),
              ),
              child: Text(tabs[i], style: TextStyle(
                fontSize: 14, fontWeight: sel ? FontWeight.w600 : FontWeight.w400,
                color: sel ? context.colors.textPrimary : context.colors.textSecondary,
              )),
            ),
          );
        }),
      ),
    );
  }

  // ── 子Tab内容 ──
  Widget _buildSubTabContent(TokenDetail token) {
    switch (_subTabIndex) {
      case 0: return _buildTradingDynamicsContent(token);
      case 1: return Padding(padding: const EdgeInsets.all(16),
                child: HolderInfoCard(token: token, goplus: _goplus, top1Pct: _top1Pct));
      case 2: return _buildLiquidityContent(token);
      case 3: return _buildDevTokenContent(token);
      default: return const SizedBox();
    }
  }

  // ── 交易动态 ──
  Widget _buildTradingDynamicsContent(TokenDetail token) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildDynamicsTimeFilter(),
        _buildTradingDynamicsGrid(token),
        const SizedBox(height: 16),
        _buildAllTradesHeader(),
        _buildTradeListHeader(),
        RecentTradesCard(
          pairAddress: _resolvedPair ?? token.pairAddress,
          network: token.geckoNetwork,
          embedded: true,
        ),
      ],
    );
  }

  Widget _buildDynamicsTimeFilter() {
    const tfs = ['5m', '1h', '4h', '24h'];
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
      child: Row(children: tfs.map((tf) {
        final sel = tf == _dynamicsTf;
        return GestureDetector(
          onTap: () => setState(() => _dynamicsTf = tf),
          child: Container(
            margin: const EdgeInsets.only(right: 8),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            decoration: BoxDecoration(
              border: Border.all(
                color: sel ? context.colors.textPrimary : const Color(0xFFD1D1D6),
                width: sel ? 1.5 : 0.5),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(tf, style: TextStyle(
              fontSize: 13, fontWeight: sel ? FontWeight.w600 : FontWeight.w400,
              color: sel ? context.colors.textPrimary : context.colors.textSecondary,
            )),
          ),
        );
      }).toList()),
    );
  }

  Widget _buildTradingDynamicsGrid(TokenDetail token) {
    final bool use1h = _dynamicsTf == '5m' || _dynamicsTf == '1h';
    final buys = use1h ? token.buys1h : token.buys24h;
    final sells = use1h ? token.sells1h : token.sells24h;
    final volume = use1h ? token.volume1hUsd : token.volume24hUsd;
    final total = buys + sells;
    final buyRatio = total > 0 ? buys / total : 0.5;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: context.colors.cardGlass, borderRadius: BorderRadius.circular(12)),
      child: Column(children: [
        _dynamicsRow('买入笔数', '$buys', '卖出笔数', '$sells', buyRatio),
        const Divider(height: 28, thickness: 0.5, color: Color(0xFFF2F2F7)),
        _dynamicsRow('成交额', _fmtWan(volume), '净买入', '${buys - sells}', buyRatio),
        const Divider(height: 28, thickness: 0.5, color: Color(0xFFF2F2F7)),
        _dynamicsRow('持有人', token.holderCount > 0 ? _fmtNum(token.holderCount) : '-',
          '流动性', _fmtWan(token.liquidityUsd), buyRatio),
      ]),
    );
  }

  Widget _dynamicsRow(String l1, String v1, String l2, String v2, double buyRatio) {
    final buyPct = (buyRatio * 100).round().clamp(1, 99);
    final sellPct = 100 - buyPct;
    return Row(children: [
      Expanded(flex: 3, child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(l1, style: TextStyle(fontSize: 11, color: context.colors.textSecondary)),
        const SizedBox(height: 4),
        Text(v1, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: context.colors.textPrimary,
          fontFeatures: [FontFeature.tabularFigures()])),
      ])),
      Expanded(flex: 3, child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(l2, style: TextStyle(fontSize: 11, color: context.colors.textSecondary)),
        const SizedBox(height: 4),
        Text(v2, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: context.colors.textPrimary,
          fontFeatures: [FontFeature.tabularFigures()])),
      ])),
      Expanded(flex: 3, child: Row(children: [
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('买/卖', style: TextStyle(fontSize: 11, color: context.colors.textSecondary)),
          const SizedBox(height: 6),
          ClipRRect(borderRadius: BorderRadius.circular(2), child: SizedBox(height: 10, child: Row(children: [
            Expanded(flex: buyPct, child: Container(color: const Color(0xFF00D4FF))),
            Expanded(flex: sellPct, child: Container(color: const Color(0xFFFF6EB4))),
          ]))),
        ])),
        const SizedBox(width: 4),
        Padding(padding: const EdgeInsets.only(top: 10),
          child: Icon(CupertinoIcons.chevron_right, size: 14, color: context.colors.textTertiary)),
      ])),
    ]);
  }

  Widget _buildAllTradesHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 6),
      child: Row(children: [
        Text('所有交易', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: context.colors.textPrimary)),
        Icon(Icons.arrow_drop_down, size: 18, color: context.colors.textSecondary),
        const Spacer(),
        Text('USD', style: TextStyle(fontSize: 13, color: context.colors.textSecondary)),
        const SizedBox(width: 4),
        Icon(CupertinoIcons.arrow_2_circlepath, size: 14, color: context.colors.textSecondary),
      ]),
    );
  }

  Widget _buildTradeListHeader() {
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 4, 16, 6),
      child: Row(children: [
        Expanded(flex: 4, child: Text('数量 / 时间', style: TextStyle(fontSize: 11, color: context.colors.textSecondary))),
        Expanded(flex: 3, child: Text('价值 / 价格', style: TextStyle(fontSize: 11, color: context.colors.textSecondary))),
        Expanded(flex: 3, child: Text('地址', style: TextStyle(fontSize: 11, color: context.colors.textSecondary), textAlign: TextAlign.right)),
      ]),
    );
  }

  Widget _buildLiquidityContent(TokenDetail token) {
    final liqMcRatio = token.marketCapUsd > 0 ? (token.liquidityUsd / token.marketCapUsd * 100) : 0.0;
    return Container(
      margin: const EdgeInsets.all(16), padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: context.colors.cardGlass, borderRadius: BorderRadius.circular(12)),
      child: Column(children: [
        _infoRow('资金池', _fmtWan(token.liquidityUsd)),
        const SizedBox(height: 12), _infoRow('市值', _fmtWan(token.marketCapUsd)),
        const SizedBox(height: 12), _infoRow('流/市值比', '${liqMcRatio.toStringAsFixed(1)}%'),
        const SizedBox(height: 12), _infoRow('24h成交额', _fmtWan(token.volume24hUsd)),
        const SizedBox(height: 12), _infoRow('1h成交额', _fmtWan(token.volume1hUsd)),
      ]),
    );
  }

  Widget _buildDevTokenContent(TokenDetail token) {
    return Container(
      margin: const EdgeInsets.all(16), padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(color: context.colors.cardGlass, borderRadius: BorderRadius.circular(12)),
      child: Column(children: [
        Icon(CupertinoIcons.doc_text_search, size: 32, color: context.colors.textTertiary),
        const SizedBox(height: 8),
        Text('暂无开发者代币数据', style: TextStyle(fontSize: 13, color: context.colors.textSecondary)),
      ]),
    );
  }

  Widget _infoRow(String label, String value) {
    return Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
      Text(label, style: TextStyle(fontSize: 13, color: context.colors.textSecondary)),
      Text(value, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: context.colors.textPrimary,
        fontFeatures: [FontFeature.tabularFigures()])),
    ]);
  }

  // ════════════════════════════════════════════════
  //  Tab 2: 详情 — Bitget 风格
  // ════════════════════════════════════════════════
  Widget _buildDetailTab(TokenDetail token) {
    return ListView(
      padding: const EdgeInsets.only(top: 0, bottom: 48),
      children: [
        _buildDetailTradingDynamics(token),
        _buildDetailKeyData(token),
        _buildDetailBasicInfo(token),
        _buildDetailAbout(token),
        _buildDetailSocialMedia(),
        _buildDetailSearchOnX(token),
        const SizedBox(height: 24),
      ],
    );
  }

  // ── Section 1: 交易动态（使用 DexScreener 实时数据） ──
  Widget _buildDetailTradingDynamics(TokenDetail token) {
    const tfs = ['5m', '1h', '4h', '24h'];
    const tfLabels = {'5m': '5分钟', '1h': '1小时', '4h': '4小时', '24h': '24小时'};

    // 优先使用 DexScreener 实时数据
    final tfData = _dexInfo?.getTimeframe(_detailDynTf);
    final int buys;
    final int sells;
    final double volume;
    final double change;

    if (tfData != null && tfData.totalTxns > 0) {
      // DexScreener 实时数据（精确到每个时间维度）
      buys = tfData.buys;
      sells = tfData.sells;
      volume = tfData.volume;
      change = tfData.priceChange;
    } else {
      // 回退到 token 静态数据
      final bool use24h = _detailDynTf == '24h' || _detailDynTf == '4h';
      buys = use24h ? token.buys24h : token.buys1h;
      sells = use24h ? token.sells24h : token.sells1h;
      volume = use24h ? token.volume24hUsd : token.volume1hUsd;
      change = switch (_detailDynTf) {
        '5m' => token.priceChange1h,
        '1h' => token.priceChange1h,
        '4h' => token.priceChange6h,
        '24h' => token.priceChange24h,
        _ => token.priceChange1h,
      };
    }
    final isPos = change >= 0;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(14),
        boxShadow: context.colors.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('交易动态', style: TextStyle(
            fontSize: 16, fontWeight: FontWeight.w700, color: context.colors.textPrimary)),
          const SizedBox(height: 12),
          // 时间筛选 pills
          Row(children: tfs.map((tf) {
            final sel = tf == _detailDynTf;
            return GestureDetector(
              onTap: () => setState(() => _detailDynTf = tf),
              child: Container(
                margin: const EdgeInsets.only(right: 8),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: sel ? context.colors.textPrimary : Colors.transparent,
                  border: Border.all(
                    color: sel ? context.colors.textPrimary : const Color(0xFFD1D1D6),
                    width: 0.5),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(tfLabels[tf] ?? tf, style: TextStyle(
                  fontSize: 13, fontWeight: sel ? FontWeight.w600 : FontWeight.w400,
                  color: sel ? Colors.white : context.colors.textSecondary,
                )),
              ),
            );
          }).toList()),
          const SizedBox(height: 16),
          // 涨跌幅
          _detailKvRow(
            '涨跌幅',
            '${isPos ? "+" : ""}${change.toStringAsFixed(2)}%',
            valueColor: isPos ? context.colors.success : context.colors.danger,
          ),
          const Divider(height: 20, thickness: 0.5, color: Color(0xFFF2F2F7)),
          // 成交量
          _detailKvRow('成交量', _fmtWan(volume)),
          const Divider(height: 20, thickness: 0.5, color: Color(0xFFF2F2F7)),
          // 成交总额（买/卖 按比例估算）
          _detailBuySellAmountRow('成交总额', volume, buys, sells),
          const Divider(height: 20, thickness: 0.5, color: Color(0xFFF2F2F7)),
          // 交易笔数（买/卖）
          _detailBuySellRow('交易笔数', buys, sells),
        ],
      ),
    );
  }

  Widget _detailKvRow(String label, String value, {Color? valueColor}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: TextStyle(fontSize: 14, color: context.colors.textSecondary)),
        Text(value, style: TextStyle(
          fontSize: 14, fontWeight: FontWeight.w600,
          color: valueColor ?? context.colors.textPrimary,
          fontFeatures: const [FontFeature.tabularFigures()],
        )),
      ],
    );
  }

  Widget _detailBuySellRow(String label, int buyVal, int sellVal) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: TextStyle(fontSize: 14, color: context.colors.textSecondary)),
        Row(children: [
          Text('$buyVal', style: TextStyle(
            fontSize: 14, fontWeight: FontWeight.w600, color: context.colors.success,
            fontFeatures: [FontFeature.tabularFigures()])),
          Text(' / ', style: TextStyle(fontSize: 14, color: context.colors.textTertiary)),
          Text('$sellVal', style: TextStyle(
            fontSize: 14, fontWeight: FontWeight.w600, color: context.colors.danger,
            fontFeatures: [FontFeature.tabularFigures()])),
        ]),
      ],
    );
  }

  Widget _detailBuySellAmountRow(String label, double totalVol, int buys, int sells) {
    final total = buys + sells;
    final buyRatio = total > 0 ? buys.toDouble() / total.toDouble() : 0.5;
    final buyAmt = totalVol * buyRatio;
    final sellAmt = totalVol * (1 - buyRatio);
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: TextStyle(fontSize: 14, color: context.colors.textSecondary)),
        Row(children: [
          Text(_fmtWan(buyAmt), style: TextStyle(
            fontSize: 14, fontWeight: FontWeight.w600, color: context.colors.success,
            fontFeatures: [FontFeature.tabularFigures()])),
          Text(' / ', style: TextStyle(fontSize: 14, color: context.colors.textTertiary)),
          Text(_fmtWan(sellAmt), style: TextStyle(
            fontSize: 14, fontWeight: FontWeight.w600, color: context.colors.danger,
            fontFeatures: [FontFeature.tabularFigures()])),
        ]),
      ],
    );
  }

  // ── Section 2: 关键数据 ──
  Widget _buildDetailKeyData(TokenDetail token) {
    final mktCap = _dexInfo?.marketCap ?? token.marketCapUsd;
    final fdv = _dexInfo?.fdv ?? mktCap;
    final holderPctStr = token.top10HolderPct != null
        ? '(${token.top10HolderPct!.toStringAsFixed(2)}%)'
        : '';
    final holderStr = token.holderCount > 0
        ? '${_fmtNum(token.holderCount)}$holderPctStr'
        : '-';

    // 流通供应量 = marketCap / price（优先用 DexScreener 实时数据）
    final livePrice = _dexInfo?.pairs.isNotEmpty == true
        ? _dexInfo!.pairs.first.priceUsd
        : token.priceUsd;
    final circulatingSupply = livePrice > 0
        ? mktCap / livePrice
        : 0.0;
    // 总流动性优先用 DexScreener 实时数据
    final liquidity = _dexInfo?.pairs.isNotEmpty == true
        ? _dexInfo!.pairs.first.liquidity
        : token.liquidityUsd;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(14),
        boxShadow: context.colors.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('关键数据', style: TextStyle(
            fontSize: 16, fontWeight: FontWeight.w700, color: context.colors.textPrimary)),
          const SizedBox(height: 14),
          _detailKvRow('流通市值', _fmtWan(mktCap)),
          const SizedBox(height: 10),
          _detailKvRow('FDV', _fmtWan(fdv)),
          const SizedBox(height: 10),
          _detailKvRow('持有人数（Top10占比）', holderStr),
          const Divider(height: 24, thickness: 0.5, color: Color(0xFFF2F2F7)),
          _detailKvRow('总流动性', _fmtWan(liquidity)),
          const SizedBox(height: 10),
          _detailKvRow('流通供应量', circulatingSupply > 0 ? _fmtSupply(circulatingSupply) : '-'),
          const SizedBox(height: 10),
          _detailKvRow('最大供应量',
            _coinGecko?.maxSupply != null ? _fmtSupply(_coinGecko!.maxSupply!) : '-'),
          const Divider(height: 24, thickness: 0.5, color: Color(0xFFF2F2F7)),
          _detailKvRow('历史最高价',
            _coinGecko?.ath != null ? '\$${_fmtPrice(_coinGecko!.ath!)}' : '-'),
          const SizedBox(height: 10),
          _detailKvRow('历史最低价',
            _coinGecko?.atl != null ? '\$${_fmtPrice(_coinGecko!.atl!)}' : '-'),
        ],
      ),
    );
  }

  String _fmtSupply(double v) {
    if (v >= 1e12) return '${(v / 1e12).toStringAsFixed(2)}万亿';
    if (v >= 1e8) return '${(v / 1e8).toStringAsFixed(2)}亿';
    if (v >= 1e4) return '${(v / 1e4).toStringAsFixed(2)}万';
    return v.toStringAsFixed(0);
  }

  // ── Section 3: 基础信息 ──
  Widget _buildDetailBasicInfo(TokenDetail token) {
    // 链图标颜色
    final chainColor = switch (token.chain) {
      'solana' => const Color(0xFF9945FF),
      'bsc' => const Color(0xFFF3BA2F),
      'base' => const Color(0xFF0052FF),
      _ => context.colors.primary,
    };
    final chainName = switch (token.chain) {
      'solana' => 'Solana',
      'bsc' => 'BNB Chain',
      'base' => 'Base',
      _ => token.chain,
    };

    // 创建时间
    String createdTimeStr = '-';
    final pairCreated = _dexInfo?.pairCreatedAt;
    if (pairCreated != null) {
      try {
        final ms = int.tryParse(pairCreated);
        final dt = ms != null
            ? DateTime.fromMillisecondsSinceEpoch(ms)
            : DateTime.parse(pairCreated);
        createdTimeStr = '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
            '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}:${dt.second.toString().padLeft(2, '0')}';
      } catch (_) {
        createdTimeStr = '-';
      }
    }

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(14),
        boxShadow: context.colors.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('基础信息', style: TextStyle(
            fontSize: 16, fontWeight: FontWeight.w700, color: context.colors.textPrimary)),
          const SizedBox(height: 14),
          // 两列：主链 + 币种全称
          Row(children: [
            Expanded(child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('主链', style: TextStyle(fontSize: 12, color: context.colors.textSecondary)),
                const SizedBox(height: 6),
                Row(children: [
                  Container(
                    width: 20, height: 20,
                    decoration: BoxDecoration(
                      color: chainColor.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    alignment: Alignment.center,
                    child: Text(chainName[0], style: TextStyle(
                      fontSize: 11, fontWeight: FontWeight.w700, color: chainColor)),
                  ),
                  const SizedBox(width: 6),
                  Text(chainName, style: TextStyle(
                    fontSize: 14, fontWeight: FontWeight.w600, color: context.colors.textPrimary)),
                ]),
              ],
            )),
            Expanded(child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('币种全称', style: TextStyle(fontSize: 12, color: context.colors.textSecondary)),
                const SizedBox(height: 6),
                Text(token.name, style: TextStyle(
                  fontSize: 14, fontWeight: FontWeight.w600, color: context.colors.textPrimary),
                  maxLines: 1, overflow: TextOverflow.ellipsis),
              ],
            )),
          ]),
          const SizedBox(height: 14),
          Text('创建时间', style: TextStyle(fontSize: 12, color: context.colors.textSecondary)),
          const SizedBox(height: 6),
          Text(createdTimeStr, style: TextStyle(
            fontSize: 14, fontWeight: FontWeight.w500, color: context.colors.textPrimary,
            fontFeatures: [FontFeature.tabularFigures()])),
        ],
      ),
    );
  }

  // ── Section 4: 关于 TOKEN ──
  Widget _buildDetailAbout(TokenDetail token) {
    // 优先 CoinGecko 描述，fallback 到 DexScreener
    final desc = (_coinGecko?.description?.isNotEmpty == true)
        ? _coinGecko!.description!
        : _dexInfo?.description;
    final hasDesc = desc != null && desc.trim().isNotEmpty;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(14),
        boxShadow: context.colors.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('关于 ${token.symbol.toUpperCase()}', style: TextStyle(
            fontSize: 16, fontWeight: FontWeight.w700, color: context.colors.textPrimary)),
          const SizedBox(height: 10),
          if (hasDesc)
            Text(desc, style: TextStyle(
              fontSize: 14, color: context.colors.textSecondary, height: 1.6),
              maxLines: 4, overflow: TextOverflow.ellipsis)
          else
            Text('暂无简介', style: TextStyle(
              fontSize: 14, color: context.colors.textTertiary)),
        ],
      ),
    );
  }

  // ── Section 5: 社交媒体 ──
  Widget _buildDetailSocialMedia() {
    final hasTwitter = _dexInfo?.twitterUrl != null && _dexInfo!.twitterUrl!.isNotEmpty;
    final hasWebsite = _dexInfo?.websiteUrl != null && _dexInfo!.websiteUrl!.isNotEmpty;
    final hasTelegram = _dexInfo?.telegramUrl != null && _dexInfo!.telegramUrl!.isNotEmpty;

    if (!hasTwitter && !hasWebsite && !hasTelegram) {
      return Container(
        margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: context.colors.cardGlass,
          borderRadius: BorderRadius.circular(14),
          boxShadow: context.colors.cardShadow,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('社交媒体', style: TextStyle(
              fontSize: 16, fontWeight: FontWeight.w700, color: context.colors.textPrimary)),
            const SizedBox(height: 12),
            Text('暂无社交信息', style: TextStyle(fontSize: 14, color: context.colors.textTertiary)),
          ],
        ),
      );
    }

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(14),
        boxShadow: context.colors.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('社交媒体', style: TextStyle(
            fontSize: 16, fontWeight: FontWeight.w700, color: context.colors.textPrimary)),
          const SizedBox(height: 12),
          Row(children: [
            if (hasTwitter) _socialCircleIcon(
              '𝕏', const Color(0xFF1DA1F2), _dexInfo!.twitterUrl!),
            if (hasTwitter) const SizedBox(width: 12),
            if (hasWebsite) _socialCircleIcon(
              null, context.colors.textSecondary, _dexInfo!.websiteUrl!,
              icon: CupertinoIcons.globe),
            if (hasWebsite && hasTelegram) const SizedBox(width: 12),
            if (hasTelegram) _socialCircleIcon(
              null, const Color(0xFF0088CC), _dexInfo!.telegramUrl!,
              icon: CupertinoIcons.paperplane_fill),
          ]),
        ],
      ),
    );
  }

  Widget _socialCircleIcon(String? text, Color color, String url, {IconData? icon}) {
    return GestureDetector(
      onTap: () async {
        final uri = Uri.parse(url);
        if (await canLaunchUrl(uri)) {
          await launchUrl(uri, mode: LaunchMode.externalApplication);
        }
      },
      child: Container(
        width: 44, height: 44,
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          shape: BoxShape.circle,
        ),
        alignment: Alignment.center,
        child: text != null
          ? Text(text, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: color))
          : Icon(icon, size: 20, color: color),
      ),
    );
  }

  // ── Section 6: 在 X 上搜索 ──
  Widget _buildDetailSearchOnX(TokenDetail token) {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.cardGlass,
        borderRadius: BorderRadius.circular(14),
        boxShadow: context.colors.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('在 X 上搜索', style: TextStyle(
            fontSize: 16, fontWeight: FontWeight.w700, color: context.colors.textPrimary)),
          const SizedBox(height: 12),
          Row(children: [
            _searchPill('搜索名称', () async {
              final query = Uri.encodeComponent('\$${token.symbol}');
              final uri = Uri.parse('https://x.com/search?q=$query');
              if (await canLaunchUrl(uri)) {
                await launchUrl(uri, mode: LaunchMode.externalApplication);
              }
            }),
            const SizedBox(width: 10),
            _searchPill('搜索地址', () async {
              final query = Uri.encodeComponent(token.address);
              final uri = Uri.parse('https://x.com/search?q=$query');
              if (await canLaunchUrl(uri)) {
                await launchUrl(uri, mode: LaunchMode.externalApplication);
              }
            }),
          ]),
        ],
      ),
    );
  }

  Widget _searchPill(String text, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: context.colors.bg,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xFFD1D1D6), width: 0.5),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Text('𝕏', style: TextStyle(
            fontSize: 13, fontWeight: FontWeight.w700, color: context.colors.textPrimary)),
          const SizedBox(width: 6),
          Text(text, style: TextStyle(
            fontSize: 13, fontWeight: FontWeight.w500, color: context.colors.textPrimary)),
        ]),
      ),
    );
  }

  // ════════════════════════════════════════════════
  //  Tab 3: 安全检测
  // ════════════════════════════════════════════════
  Widget _buildSecurityTab() {
    return ListView(
      padding: const EdgeInsets.only(top: 12, bottom: 48),
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text('本工具旨在提供代币安全性辅助判断，不应作为投资依据或推荐。请在交易前自行评估风险。',
            style: TextStyle(fontSize: 13, color: context.colors.textSecondary, height: 1.5)),
        ),
        const SizedBox(height: 16),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(children: [
            _riskStat('风险项', _goplus?.dangerCount ?? 0, context.colors.danger),
            const SizedBox(width: 16),
            _riskStat('警示项', _goplus?.warningCount ?? 0, context.colors.warning),
          ]),
        ),
        const SizedBox(height: 16),
        SecurityCheckCard(report: _goplus, loading: _goplusLoading),
      ],
    );
  }

  // ════════════════════════════════════════════════
  //  Helper Widgets
  // ════════════════════════════════════════════════
  Widget _miniAvatar(TokenDetail token) {
    final c = switch (token.chain) {
      'solana' => const Color(0xFF9945FF), 'bsc' => const Color(0xFFF3BA2F),
      'base' => const Color(0xFF0052FF), _ => context.colors.primary,
    };
    return Container(width: 28, height: 28,
      decoration: BoxDecoration(
        gradient: LinearGradient(colors: [c.withValues(alpha: 0.15), c.withValues(alpha: 0.05)]),
        borderRadius: BorderRadius.circular(14)),
      alignment: Alignment.center,
      child: Text(token.symbol.isNotEmpty ? token.symbol[0].toUpperCase() : '?',
        style: TextStyle(color: c, fontSize: 13, fontWeight: FontWeight.w800)));
  }

  Widget _riskStat(String label, int count, Color color) {
    return Expanded(child: Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.colors.cardGlass, borderRadius: BorderRadius.circular(14),
        boxShadow: context.colors.cardShadow,
        border: count > 0 ? Border.all(color: color.withValues(alpha: 0.15), width: 1) : null),
      child: Row(children: [
        Container(width: 36, height: 36,
          decoration: BoxDecoration(
            color: (count > 0 ? color : context.colors.textTertiary).withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(10)),
          alignment: Alignment.center,
          child: Icon(CupertinoIcons.exclamationmark_circle, size: 20,
            color: count > 0 ? color : context.colors.textTertiary)),
        const SizedBox(width: 12),
        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: TextStyle(fontSize: 12, color: context.colors.textSecondary)),
          const SizedBox(height: 2),
          Text('$count', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800,
            color: count > 0 ? color : context.colors.textPrimary,
            fontFeatures: const [FontFeature.tabularFigures()])),
        ]),
      ]),
    ));
  }

  Widget _bitgetTag(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        border: Border.all(color: color.withValues(alpha: 0.4), width: 0.5),
        borderRadius: BorderRadius.circular(4)),
      child: Text(text, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w500, color: color)));
  }

  Widget _statRow(String label, String value) {
    return Padding(padding: const EdgeInsets.only(bottom: 5), child: Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(label, style: TextStyle(fontSize: 12, color: context.colors.textSecondary)),
        Text(value, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: context.colors.textPrimary,
          fontFeatures: [FontFeature.tabularFigures()])),
      ]));
  }

  String _fmtPrice(double p) {
    if (p >= 1000) return '\$${p.toStringAsFixed(0)}';
    if (p >= 1) return '\$${p.toStringAsFixed(2)}';
    if (p >= 0.01) return '\$${p.toStringAsFixed(4)}';
    if (p >= 0.0001) return '\$${p.toStringAsFixed(6)}';
    return '\$${p.toStringAsFixed(8)}';
  }

  String _fmtWan(double v) {
    if (v <= 0) return '-';
    if (v >= 1e8) return '\$${(v / 1e8).toStringAsFixed(2)}亿';
    if (v >= 1e4) return '\$${(v / 1e4).toStringAsFixed(2)}万';
    return '\$${v.toStringAsFixed(2)}';
  }

  String _fmtNum(int n) {
    if (n >= 1000000) return '${(n / 1000000).toStringAsFixed(1)}M';
    if (n >= 10000) return '${(n / 10000).toStringAsFixed(1)}万';
    if (n >= 1000) {
      final s = n.toString();
      return '${s.substring(0, s.length - 3)},${s.substring(s.length - 3)}';
    }
    return '$n';
  }
}

// ═══════════════════════════════════════════════════════
//  吸顶 Header Delegate — 子Tab滑到顶部时固定
// ═══════════════════════════════════════════════════════
class _StickyHeaderDelegate extends SliverPersistentHeaderDelegate {
  final Widget child;
  final double height;

  _StickyHeaderDelegate({required this.child, required this.height});

  @override
  Widget build(BuildContext context, double shrinkOffset, bool overlapsContent) {
    return SizedBox.expand(child: child);
  }

  @override
  double get maxExtent => height;

  @override
  double get minExtent => height;

  @override
  bool shouldRebuild(covariant _StickyHeaderDelegate old) => true;
}
