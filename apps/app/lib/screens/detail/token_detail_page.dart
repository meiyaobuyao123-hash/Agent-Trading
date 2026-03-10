import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import '../../models/token_detail.dart';
import '../../models/ohlcv_data.dart';
import '../../models/goplus_report.dart';
import '../../models/dexscreener_info.dart';
import '../../services/token_detail_service.dart';
import '../../services/gecko_terminal_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/detail/detail_header.dart';
import '../../widgets/detail/tradingview_chart.dart';
import '../../widgets/detail/market_stats_grid.dart';
import '../../widgets/detail/score_breakdown_card.dart';
import '../../widgets/detail/bc_progress_card.dart';
import '../../widgets/detail/bottom_tabs_section.dart';
import '../../widgets/detail/shimmer_skeleton.dart';

class TokenDetailPage extends StatefulWidget {
  final TokenDetail token;
  const TokenDetailPage({super.key, required this.token});

  @override
  State<TokenDetailPage> createState() => _TokenDetailPageState();
}

class _TokenDetailPageState extends State<TokenDetailPage> {
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
    _loadEnrichment();
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
        _candleCache[tf] = data ?? [];
        setState(() { _candles = data ?? []; _candleLoading = false; });
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

  @override
  Widget build(BuildContext context) {
    final token = widget.token;

    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        backgroundColor: AppColors.bg,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        surfaceTintColor: Colors.transparent,
        centerTitle: true,
        title: Text(token.symbol.toUpperCase(),
            style: const TextStyle(
              fontWeight: FontWeight.w600, fontSize: 17,
              color: AppColors.textPrimary,
            )),
        leading: IconButton(
          icon: const Icon(CupertinoIcons.back, size: 22),
          color: AppColors.textPrimary,
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: _enrichLoading
          ? const SingleChildScrollView(
              padding: EdgeInsets.only(top: 8, bottom: 40),
              child: ShimmerSkeleton(),
            )
          : ListView(
              padding: const EdgeInsets.only(top: 4, bottom: 48),
              children: _buildContent(token),
            ),
    );
  }

  List<Widget> _buildContent(TokenDetail token) {
    return [
      // 1. 头部
      DetailHeader(token: token, imageUrl: _dexInfo?.imageUrl),
      const SizedBox(height: 16),

      // 2. DailyPick: BC 进度
      if (token.isDailyPick && token.bcProgress != null) ...[
        BcProgressCard(token: token),
        const SizedBox(height: 16),
      ],

      // 3. TradingView K线图 + MA7/MA25
      TradingViewChart(
        candles: _candles,
        selectedTimeframe: _timeframe,
        onTimeframeChanged: _switchTimeframe,
        loading: _candleLoading,
      ),
      const SizedBox(height: 16),

      // 4. 市场指标
      MarketStatsGrid(token: token),
      const SizedBox(height: 16),

      // 5. AI 评分
      ScoreBreakdownCard(token: token),
      const SizedBox(height: 16),

      // 6. 底部三 Tab：交易动态 / 安全检测 / 代币信息
      BottomTabsSection(
        token: token,
        goplus: _goplus,
        dexInfo: _dexInfo,
        top1Pct: _top1Pct,
        goplusLoading: _goplusLoading,
        resolvedPair: _resolvedPair,
      ),

      // TradingView 归属
      const Padding(
        padding: EdgeInsets.fromLTRB(16, 20, 16, 0),
        child: Text(
          'Charts by TradingView',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 11, color: AppColors.textTertiary),
        ),
      ),
    ];
  }
}
