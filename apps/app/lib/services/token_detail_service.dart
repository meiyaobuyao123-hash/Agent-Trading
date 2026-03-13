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
    // 并行调用所有外部 API（具名 Future，避免下标脆弱）
    final goplusFuture   = GoPlusService.instance.fetchReport(chain: chain, address: address);
    final dexFuture      = DexScreenerService.instance.fetchTokenInfo(address);
    final coinGeckoFuture = CoinGeckoService.instance.fetchTokenInfo(chain: chain, address: address);

    Future<List<Map<String, dynamic>>> solHoldersFuture = Future.value([]);
    Future<List<TokenHolder>> evmHoldersFuture = Future.value([]);

    if (chain == 'solana') {
      solHoldersFuture = HeliusService.instance.fetchLargestHolders(address);
    } else if (chain == 'bsc' || chain == 'base' || chain == 'eth') {
      evmHoldersFuture = EvmExplorerService.instance.fetchTopHolders(
        chain: chain, contractAddress: address, limit: 20,
      );
    }

    final results = await Future.wait([
      goplusFuture, dexFuture, coinGeckoFuture, solHoldersFuture, evmHoldersFuture,
    ]);

    final goplus      = results[0] as GoPlusReport?;
    final dexInfo     = results[1] as DexScreenerInfo?;
    final coinGeckoInfo = results[2] as CoinGeckoTokenInfo?;

    // 根据链类型解析 holder 数据
    double? top1Pct;
    double? top10Pct;

    if (chain == 'solana') {
      final holders = results[3] as List<Map<String, dynamic>>;
      if (holders.isNotEmpty) {
        top1Pct = holders.first['pct'] as double?;
        final top10Sum = holders.take(10).fold<double>(0, (s, h) => s + ((h['pct'] as double?) ?? 0));
        top10Pct = top10Sum;
      }
    } else if (chain == 'bsc' || chain == 'base' || chain == 'eth') {
      final holders = results[4] as List<TokenHolder>;
      if (holders.isNotEmpty) {
        final totalOfTop = holders.fold<double>(0, (s, h) => s + h.quantity);
        if (totalOfTop > 0) {
          top1Pct = (holders.first.quantity / totalOfTop) * 100;
          final top10Sum = holders.take(10).fold<double>(0, (s, h) => s + h.quantity);
          top10Pct = (top10Sum / totalOfTop) * 100;
        }
      }
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
      top10HolderPctRpc: top10Pct,   // 链 RPC 精确 Top10 占比
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
  final double? top10HolderPctRpc;  // 链 RPC 精确 Top10 占比（优先于 GoPlus）
  final List<OhlcvCandle> initialCandles;
  final String? resolvedPairAddress;
  final CoinGeckoTokenInfo? coinGeckoInfo;

  const TokenEnrichment({
    this.goplusReport,
    this.dexScreenerInfo,
    this.top1HolderPct,
    this.top10HolderPctRpc,
    required this.initialCandles,
    this.resolvedPairAddress,
    this.coinGeckoInfo,
  });
}
