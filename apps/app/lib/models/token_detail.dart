import 'hot_coin.dart';
import 'daily_pick.dart';

enum TokenSource { hotCoin, dailyPick }

/// 统一代币详情模型 — 从 HotCoin 或 DailyPick 构造
class TokenDetail {
  final String chain;
  final String address;
  final String name;
  final String symbol;
  final String? pairAddress;
  final String? dexId;

  final double priceUsd;
  final double marketCapUsd;
  final double liquidityUsd;
  final double volume5mUsd;
  final double volume1hUsd;
  final double volume4hUsd;
  final double volume24hUsd;

  final double priceChange5m;
  final double priceChange1h;
  final double priceChange4h;
  final double priceChange6h;
  final double priceChange24h;

  final int buys1h;
  final int sells1h;
  final int buys24h;
  final int sells24h;

  final double ageDays;
  final int holderCount;
  final double? top10HolderPct;
  final double? top1HolderPct;

  final bool goplusRisk;
  final bool hasTwitter;
  final bool hasTelegram;
  final bool hasWebsite;

  final double score;
  final double? scoreM;
  final double? scoreQ;
  final double? scoreP;
  final Map<String, dynamic>? scoreDetail;
  final String recommendation;

  final TokenSource source;

  // DailyPick 专属
  final double? bcProgress;
  final bool? didGraduate;
  final double? peakMultiplier;
  final bool? label2x;
  final bool? label10x;
  final String? imageUri;

  const TokenDetail({
    required this.chain,
    required this.address,
    required this.name,
    required this.symbol,
    this.pairAddress,
    this.dexId,
    required this.priceUsd,
    required this.marketCapUsd,
    required this.liquidityUsd,
    this.volume5mUsd = 0,
    required this.volume1hUsd,
    this.volume4hUsd = 0,
    required this.volume24hUsd,
    this.priceChange5m = 0,
    required this.priceChange1h,
    this.priceChange4h = 0,
    required this.priceChange6h,
    required this.priceChange24h,
    required this.buys1h,
    required this.sells1h,
    required this.buys24h,
    required this.sells24h,
    required this.ageDays,
    required this.holderCount,
    this.top10HolderPct,
    this.top1HolderPct,
    required this.goplusRisk,
    required this.hasTwitter,
    required this.hasTelegram,
    required this.hasWebsite,
    required this.score,
    this.scoreM,
    this.scoreQ,
    this.scoreP,
    this.scoreDetail,
    required this.recommendation,
    required this.source,
    this.bcProgress,
    this.didGraduate,
    this.peakMultiplier,
    this.label2x,
    this.label10x,
    this.imageUri,
  });

  factory TokenDetail.fromHotCoin(HotCoin coin) {
    return TokenDetail(
      chain: coin.chain,
      address: coin.address,
      name: coin.name,
      symbol: coin.symbol,
      pairAddress: coin.pairAddress,
      dexId: coin.dexId,
      priceUsd: coin.priceUsd,
      marketCapUsd: coin.marketCapUsd,
      liquidityUsd: coin.liquidityUsd,
      volume5mUsd: coin.volume5mUsd,
      volume1hUsd: coin.volume1hUsd,
      volume4hUsd: coin.volume4hUsd,
      volume24hUsd: coin.volume24hUsd,
      priceChange5m: coin.priceChange5m,
      priceChange1h: coin.priceChange1h,
      priceChange4h: coin.priceChange4h,
      priceChange6h: coin.priceChange6h,
      priceChange24h: coin.priceChange24h,
      buys1h: coin.buys1h,
      sells1h: coin.sells1h,
      buys24h: coin.buys24h,
      sells24h: coin.sells24h,
      ageDays: coin.ageDays,
      holderCount: coin.holderCount,
      top10HolderPct: coin.top10HolderPct,
      top1HolderPct: coin.top1HolderPct,
      goplusRisk: coin.goplusRisk,
      hasTwitter: coin.hasTwitter,
      hasTelegram: coin.hasTelegram,
      hasWebsite: coin.hasWebsite,
      score: coin.score,
      scoreM: coin.scoreM,
      scoreQ: coin.scoreQ,
      scoreP: coin.scoreP,
      recommendation: coin.recommendation,
      source: TokenSource.hotCoin,
      imageUri: coin.imageUrl,
    );
  }

  factory TokenDetail.fromDailyPick(DailyPick pick) {
    return TokenDetail(
      chain: 'solana',
      address: pick.mint,
      name: pick.name,
      symbol: pick.symbol,
      priceUsd: 0,
      marketCapUsd: 0,
      liquidityUsd: 0,
      volume24hUsd: 0,
      volume1hUsd: 0,
      priceChange1h: 0,
      priceChange6h: 0,
      priceChange24h: 0,
      buys1h: 0,
      sells1h: 0,
      buys24h: 0,
      sells24h: 0,
      ageDays: 0,
      holderCount: 0,
      goplusRisk: false,
      hasTwitter: pick.twitter != null,
      hasTelegram: pick.telegram != null,
      hasWebsite: pick.website != null,
      score: pick.score,
      scoreDetail: pick.scoreDetail,
      recommendation: pick.recommendation,
      source: TokenSource.dailyPick,
      bcProgress: pick.bcProgress,
      didGraduate: pick.didGraduate,
      peakMultiplier: pick.peakMultiplier,
      label2x: pick.label2x,
      label10x: pick.label10x,
      imageUri: pick.imageUri,
    );
  }

  // ── 链相关计算属性 ────────────────────────────
  String get geckoNetwork => chain; // solana, bsc, base 均匹配

  String get goplusChainId => switch (chain) {
        'solana' => 'solana',
        'bsc' => '56',
        'base' => '8453',
        'eth' => '1',
        _ => chain,
      };

  String get explorerTokenUrl => switch (chain) {
        'solana' => 'https://solscan.io/token/$address',
        'bsc' => 'https://bscscan.com/token/$address',
        'base' => 'https://basescan.org/token/$address',
        'eth' => 'https://etherscan.io/token/$address',
        _ => '',
      };

  String get dexScreenerUrl {
    final addr = pairAddress ?? address;
    return 'https://dexscreener.com/$chain/$addr';
  }

  String get geckoTerminalUrl =>
      'https://www.geckoterminal.com/$chain/pools/${pairAddress ?? address}';

  String get chainLabel => switch (chain) {
        'solana' => 'SOL',
        'bsc' => 'BSC',
        'base' => 'BASE',
        'eth' => 'ETH',
        _ => chain.toUpperCase(),
      };

  double get buySellRatio1h {
    final total = buys1h + sells1h;
    return total > 0 ? buys1h / total : 0.5;
  }

  double get buySellRatio24h {
    final total = buys24h + sells24h;
    return total > 0 ? buys24h / total : 0.5;
  }

  bool get isDailyPick => source == TokenSource.dailyPick;
}
