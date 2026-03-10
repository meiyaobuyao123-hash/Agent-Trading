import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../models/token_detail.dart';
import '../../models/ohlcv_data.dart';
import '../../models/goplus_report.dart';
import '../../models/dexscreener_info.dart';
import '../../services/token_detail_service.dart';
import '../../services/gecko_terminal_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/detail/tradingview_chart.dart';
import '../../widgets/detail/market_stats_grid.dart';
import '../../widgets/detail/score_breakdown_card.dart';
import '../../widgets/detail/bc_progress_card.dart';
import '../../widgets/detail/trading_dynamics_card.dart';
import '../../widgets/detail/recent_trades_card.dart';
import '../../widgets/detail/holder_info_card.dart';
import '../../widgets/detail/security_check_card.dart';
import '../../widgets/detail/social_links_bar.dart';
import '../../widgets/detail/contract_address_card.dart';
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
  double? _top1Pct;
  String? _resolvedPair;

  List<OhlcvCandle> _candles = [];
  String _timeframe = '1h';
  bool _candleLoading = true;
  final Map<String, List<OhlcvCandle>> _candleCache = {};

  bool _enrichLoading = true;
  bool _goplusLoading = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
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

  @override
  Widget build(BuildContext context) {
    final token = widget.token;
    final shortAddr = '${token.address.substring(0, 6)}...${token.address.substring(token.address.length - 4)}';
    final imageUrl = _dexInfo?.imageUrl ?? token.imageUri;

    return Scaffold(
      backgroundColor: AppColors.bg,
      body: NestedScrollView(
        headerSliverBuilder: (context, _) => [
          // ── Bitget 风格固定 Header ──────────────
          SliverAppBar(
            pinned: true,
            backgroundColor: AppColors.bg,
            elevation: 0,
            scrolledUnderElevation: 0.5,
            surfaceTintColor: Colors.transparent,
            leading: IconButton(
              icon: const Icon(CupertinoIcons.back, size: 22),
              color: AppColors.textPrimary,
              onPressed: () => Navigator.of(context).pop(),
            ),
            title: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                // 代币 Icon
                if (imageUrl != null && imageUrl.isNotEmpty)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(14),
                    child: Image.network(imageUrl, width: 28, height: 28, fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => _miniAvatar(token)),
                  )
                else
                  _miniAvatar(token),
                const SizedBox(width: 8),
                // 名称
                Text(token.symbol.toUpperCase(),
                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 18, color: AppColors.textPrimary)),
                const SizedBox(width: 4),
                Icon(CupertinoIcons.chevron_down, size: 14, color: AppColors.textSecondary),
              ],
            ),
            actions: [
              // 合约短地址 + 复制
              GestureDetector(
                onTap: _copyAddress,
                child: Container(
                  margin: const EdgeInsets.only(right: 4),
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.bg,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    Text(shortAddr, style: const TextStyle(fontSize: 11, color: AppColors.textSecondary, fontFamily: 'Menlo')),
                    const SizedBox(width: 2),
                    Icon(CupertinoIcons.doc_on_clipboard, size: 11, color: AppColors.textTertiary),
                  ]),
                ),
              ),
              // 天数
              if (token.ageDays > 0)
                Container(
                  margin: const EdgeInsets.only(right: 4),
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                  decoration: BoxDecoration(color: AppColors.bg, borderRadius: BorderRadius.circular(6)),
                  child: Text('${token.ageDays.toStringAsFixed(0)}天',
                    style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
                ),
              const SizedBox(width: 8),
            ],
            bottom: TabBar(
              controller: _tabController,
              labelColor: AppColors.textPrimary,
              unselectedLabelColor: AppColors.textSecondary,
              labelStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
              unselectedLabelStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w400),
              indicatorColor: AppColors.primary,
              indicatorWeight: 2.5,
              indicatorSize: TabBarIndicatorSize.label,
              tabs: const [
                Tab(text: '行情'),
                Tab(text: '详情'),
                Tab(text: '安全检测'),
              ],
            ),
          ),
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

  Widget _miniAvatar(TokenDetail token) {
    final c = switch (token.chain) {
      'solana' => const Color(0xFF9945FF),
      'bsc' => const Color(0xFFF3BA2F),
      'base' => const Color(0xFF0052FF),
      _ => AppColors.primary,
    };
    return Container(
      width: 28, height: 28,
      decoration: BoxDecoration(
        gradient: LinearGradient(colors: [c.withValues(alpha: 0.15), c.withValues(alpha: 0.05)]),
        borderRadius: BorderRadius.circular(14),
      ),
      alignment: Alignment.center,
      child: Text(token.symbol.isNotEmpty ? token.symbol[0].toUpperCase() : '?',
        style: TextStyle(color: c, fontSize: 13, fontWeight: FontWeight.w800)),
    );
  }

  // ════════════════════════════════════════════════
  // Tab 1: 行情
  // ════════════════════════════════════════════════
  Widget _buildMarketTab(TokenDetail token) {
    return ListView(
      padding: const EdgeInsets.only(top: 8, bottom: 48),
      children: [
        // 价格区域
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (token.priceUsd > 0)
                Text(_fmtPrice(token.priceUsd),
                  style: const TextStyle(fontSize: 32, fontWeight: FontWeight.w800,
                    color: AppColors.textPrimary, letterSpacing: -1.5, height: 1.1)),
              const SizedBox(height: 4),
              Row(children: [
                _changePill(token.priceChange24h, '24h'),
                const SizedBox(width: 6),
                if (token.recommendation == 'strong')
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF0F0F0), borderRadius: BorderRadius.circular(4)),
                    child: const Text('Hot Picks', style: TextStyle(fontSize: 10, color: AppColors.textSecondary)),
                  ),
              ]),
            ],
          ),
        ),
        const SizedBox(height: 8),

        // AI 评价行
        if (token.scoreDetail != null && token.scoreDetail!.isNotEmpty)
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 16),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(3)),
                child: const Text('AI', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: AppColors.primary)),
              ),
              const SizedBox(width: 8),
              Expanded(child: Text(
                'AI评分 ${token.score.toStringAsFixed(0)} · ${token.recommendation == "strong" ? "强推" : "关注"}',
                style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                overflow: TextOverflow.ellipsis,
              )),
              const Icon(CupertinoIcons.chevron_right, size: 12, color: AppColors.textTertiary),
            ]),
          ),
        const SizedBox(height: 12),

        // BC 进度（pump.fun 内盘）
        if (token.isDailyPick && token.bcProgress != null) ...[
          BcProgressCard(token: token),
          const SizedBox(height: 12),
        ],

        // K线图
        TradingViewChart(
          candles: _candles,
          selectedTimeframe: _timeframe,
          onTimeframeChanged: _switchTimeframe,
          loading: _candleLoading,
        ),
        const SizedBox(height: 16),

        // AI 评分卡片
        ScoreBreakdownCard(token: token),
        const SizedBox(height: 16),

        // 交易动态
        if (token.buys1h + token.sells1h > 0 || token.buys24h + token.sells24h > 0) ...[
          TradingDynamicsCard(token: token),
          const SizedBox(height: 16),
        ],

        // 逐笔交易
        RecentTradesCard(
          pairAddress: _resolvedPair ?? token.pairAddress,
          network: token.geckoNetwork,
        ),

        // TradingView 归属
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 20, 16, 0),
          child: Text('Charts by TradingView',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 11, color: AppColors.textTertiary)),
        ),
      ],
    );
  }

  // ════════════════════════════════════════════════
  // Tab 2: 详情
  // ════════════════════════════════════════════════
  Widget _buildDetailTab(TokenDetail token) {
    return ListView(
      padding: const EdgeInsets.only(top: 12, bottom: 48),
      children: [
        // 价格 + 涨跌（小版本）
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (token.priceUsd > 0)
                Row(children: [
                  Text('\$${token.priceUsd.toStringAsFixed(token.priceUsd >= 1 ? 2 : 6)}',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
                  const SizedBox(width: 8),
                  _changePill(token.priceChange24h, '24h'),
                ]),
              const SizedBox(height: 16),

              // 关键数据
              const Text('关键数据', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
              const SizedBox(height: 12),
            ],
          ),
        ),

        // 市场指标网格
        MarketStatsGrid(token: token),
        const SizedBox(height: 16),

        // 持有者
        HolderInfoCard(token: token, goplus: _goplus, top1Pct: _top1Pct),
        const SizedBox(height: 16),

        // 社交链接
        SocialLinksBar(info: _dexInfo),
        const SizedBox(height: 16),

        // 合约地址
        ContractAddressCard(token: token),
      ],
    );
  }

  // ════════════════════════════════════════════════
  // Tab 3: 安全检测
  // ════════════════════════════════════════════════
  Widget _buildSecurityTab() {
    return ListView(
      padding: const EdgeInsets.only(top: 12, bottom: 48),
      children: [
        // 安全声明
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text(
            '本工具旨在提供代币安全性辅助判断，不应作为投资依据或推荐。请在交易前自行评估风险。',
            style: TextStyle(fontSize: 13, color: AppColors.textSecondary, height: 1.5),
          ),
        ),
        const SizedBox(height: 16),

        // 风险/警示统计
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(children: [
            _riskStat('风险项', _goplus?.dangerCount ?? 0, AppColors.danger),
            const SizedBox(width: 16),
            _riskStat('警示项', _goplus?.warningCount ?? 0, AppColors.warning),
          ]),
        ),
        const SizedBox(height: 16),

        // 安全检测卡片
        SecurityCheckCard(report: _goplus, loading: _goplusLoading),
      ],
    );
  }

  Widget _riskStat(String label, int count, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          boxShadow: const [BoxShadow(color: Color(0x08000000), blurRadius: 8, offset: Offset(0, 2))],
        ),
        child: Row(children: [
          Icon(CupertinoIcons.exclamationmark_circle, size: 28, color: count > 0 ? color : AppColors.textTertiary),
          const SizedBox(width: 10),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
            Text('$count', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800,
              color: count > 0 ? color : AppColors.textPrimary)),
          ]),
        ]),
      ),
    );
  }

  Widget _changePill(double pct, String label) {
    final isPos = pct >= 0;
    final color = isPos ? AppColors.success : AppColors.danger;
    final sign = isPos ? '+' : '';
    return Text('$sign${pct.toStringAsFixed(2)}%',
      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: color));
  }

  String _fmtPrice(double p) {
    if (p >= 1) return '\$${p.toStringAsFixed(2)}';
    if (p >= 0.01) return '\$${p.toStringAsFixed(4)}';
    if (p >= 0.0001) return '\$${p.toStringAsFixed(6)}';
    return '\$${p.toStringAsFixed(8)}';
  }
}
