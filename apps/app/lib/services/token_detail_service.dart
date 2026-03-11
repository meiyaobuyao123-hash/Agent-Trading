import '../models/ohlcv_data.dart';
import '../models/goplus_report.dart';
import '../models/dexscreener_info.dart';
import 'gecko_terminal_service.dart';
import 'goplus_service.dart';
import 'dexscreener_service.dart';
import 'helius_service.dart';
import 'coingecko_service.dart';
import 'evm_explorer_service.dart';

/// 详情页数据编排 — 并行调用所有外部 API
class TokenDetailService {
  static final TokenDetailService instance = TokenDetailService._();
  TokenDetailService._();

  /// 加载详情页 enrichment 数据
  Future<TokenEnrichment> loadEnrichment({
    required String chain,
    required String address,
    String? pairAddress,
  }) async {
    // 并行调用 GoPlus + DexScreener + Helius(SOL) + CoinGecko + EvmExplorer(BSC/Base)
    final futures = <Future>[
      GoPlusService.instance.fetchReport(chain: chain, address: address),
      DexScreenerService.instance.fetchTokenInfo(address),
      if (chain == 'solana')
        HeliusService.instance.fetchTop1HolderPct(address),
      if (chain == 'bsc' || chain == 'base')
        EvmExplorerService.instance.fetchTop1HolderPct(
          chain: chain, contractAddress: address,
        ),
      CoinGeckoService.instance.fetchTokenInfo(chain: chain, address: address),
    ];

    final results = await Future.wait(futures);

    final goplus = results[0] as GoPlusReport?;
    final dexInfo = results[1] as DexScreenerInfo?;

    // 根据链类型获取 Top1 持仓和 CoinGecko 数据位置
    double? top1Pct;
    CoinGeckoTokenInfo? coinGeckoInfo;

    if (chain == 'solana') {
      top1Pct = results[2] as double?;
      coinGeckoInfo = results[3] as CoinGeckoTokenInfo?;
    } else if (chain == 'bsc' || chain == 'base') {
      top1Pct = results[2] as double?;
      coinGeckoInfo = results[3] as CoinGeckoTokenInfo?;
    } else {
      coinGeckoInfo = results[2] as CoinGeckoTokenInfo?;
    }

    // 解析 pair address — 优先级: 传入 > DexScreener > 代币地址
    String? resolvedPair = pairAddress;
    if (resolvedPair == null || resolvedPair.isEmpty) {
      if (dexInfo?.pairs.isNotEmpty == true) {
        resolvedPair = dexInfo!.pairs.first.pairAddress;
      }
    }

    // 加载默认 1h K线 — 先用 resolvedPair，失败则用 address 作 fallback
    List<OhlcvCandle>? candles;
    if (resolvedPair != null && resolvedPair.isNotEmpty) {
      candles = await GeckoTerminalService.instance.fetchOhlcv(
        network: chain,
        poolAddress: resolvedPair,
        timeframe: 'hour',
        aggregate: 1,
        limit: 100,
      );
    }
    // fallback: 用代币 address 直接查 GeckoTerminal（部分 pool 可匹配）
    if ((candles == null || candles.isEmpty) && (resolvedPair == null || resolvedPair != address)) {
      try {
        final fallback = await GeckoTerminalService.instance.fetchOhlcv(
          network: chain,
          poolAddress: address,
          timeframe: 'hour',
          aggregate: 1,
          limit: 100,
        );
        if (fallback.isNotEmpty) {
          candles = fallback;
          resolvedPair = address;
        }
      } catch (_) {
        // 静默失败
      }
    }

    return TokenEnrichment(
      goplusReport: goplus,
      dexScreenerInfo: dexInfo,
      top1HolderPct: top1Pct,
      initialCandles: candles ?? [],
      resolvedPairAddress: resolvedPair,
      coinGeckoInfo: coinGeckoInfo,
    );
  }
}

class TokenEnrichment {
  final GoPlusReport? goplusReport;
  final DexScreenerInfo? dexScreenerInfo;
  final double? top1HolderPct;
  final List<OhlcvCandle> initialCandles;
  final String? resolvedPairAddress;
  final CoinGeckoTokenInfo? coinGeckoInfo;

  const TokenEnrichment({
    this.goplusReport,
    this.dexScreenerInfo,
    this.top1HolderPct,
    required this.initialCandles,
    this.resolvedPairAddress,
    this.coinGeckoInfo,
  });
}
