/// 多链热币榜模型
/// 对应 Supabase `hot_coins` 表（OKX 主数据源 + GoPlus + Helius + DexScreener 富化）
/// 覆盖链：SOL / BSC / Base / ETH
class HotCoin {
  final String chain;          // 'solana' | 'bsc' | 'base' | 'eth'
  final String address;        // 代币合约地址
  final String name;
  final String symbol;
  final String? pairAddress;
  final String? dexId;         // 'raydium' | 'pancakeswap' | 'aerodrome' 等

  // 市场数据（OKX 毫秒级更新）
  final double priceUsd;
  final double marketCapUsd;
  final double liquidityUsd;
  final double volume5mUsd;    // OKX 5分钟成交量
  final double volume1hUsd;
  final double volume4hUsd;    // OKX 4小时成交量
  final double volume24hUsd;

  // 价格变化（OKX 聚合窗口）
  final double priceChange5m;  // OKX 5分钟涨跌
  final double priceChange1h;
  final double priceChange4h;  // OKX 4小时涨跌
  final double priceChange6h;
  final double priceChange24h;

  // 交易活跃度
  final int buys1h;
  final int sells1h;
  final int buys24h;
  final int sells24h;

  // 年龄
  final double ageDays;

  // 持有者
  final int holderCount;
  final double? top10HolderPct;   // GoPlus top10 持仓比例
  final double? top1HolderPct;    // Helius SOL精确 top1（其他链为null）

  // 安全
  final bool goplusRisk;          // 任何风险标记

  // 社交
  final bool hasTwitter;
  final bool hasTelegram;
  final bool hasWebsite;

  // 图标
  final String? imageUrl;

  // 打分
  final double score;             // 综合分 0-100
  final double scoreM;            // 动量分 0-50
  final double scoreQ;            // 品质分 0-30
  final double scoreP;            // 潜力分 0-20
  final String recommendation;    // 'strong' | 'normal' | 'skip'

  final String scannedAt;

  const HotCoin({
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
    this.imageUrl,
    required this.score,
    required this.scoreM,
    required this.scoreQ,
    required this.scoreP,
    required this.recommendation,
    required this.scannedAt,
  });

  factory HotCoin.fromJson(Map<String, dynamic> json) {
    return HotCoin(
      chain:           json['chain']          as String? ?? '',
      address:         json['address']        as String? ?? '',
      name:            json['name']           as String? ?? '',
      symbol:          json['symbol']         as String? ?? '',
      pairAddress:     json['pair_address']   as String?,
      dexId:           json['dex_id']         as String?,
      priceUsd:        (json['price_usd']         as num?)?.toDouble() ?? 0.0,
      marketCapUsd:    (json['market_cap_usd']     as num?)?.toDouble() ?? 0.0,
      liquidityUsd:    (json['liquidity_usd']      as num?)?.toDouble() ?? 0.0,
      volume5mUsd:     (json['volume_5m_usd']      as num?)?.toDouble() ?? 0.0,
      volume1hUsd:     (json['volume_1h_usd']      as num?)?.toDouble() ?? 0.0,
      volume4hUsd:     (json['volume_4h_usd']      as num?)?.toDouble() ?? 0.0,
      volume24hUsd:    (json['volume_24h_usd']     as num?)?.toDouble() ?? 0.0,
      priceChange5m:   (json['price_change_5m']    as num?)?.toDouble() ?? 0.0,
      priceChange1h:   (json['price_change_1h']    as num?)?.toDouble() ?? 0.0,
      priceChange4h:   (json['price_change_4h']    as num?)?.toDouble() ?? 0.0,
      priceChange6h:   (json['price_change_6h']    as num?)?.toDouble() ?? 0.0,
      priceChange24h:  (json['price_change_24h']   as num?)?.toDouble() ?? 0.0,
      buys1h:          (json['buys_1h']            as num?)?.toInt()    ?? 0,
      sells1h:         (json['sells_1h']           as num?)?.toInt()    ?? 0,
      buys24h:         (json['buys_24h']           as num?)?.toInt()    ?? 0,
      sells24h:        (json['sells_24h']          as num?)?.toInt()    ?? 0,
      ageDays:         (json['age_days']           as num?)?.toDouble() ?? 0.0,
      holderCount:     (json['holder_count']       as num?)?.toInt()    ?? 0,
      top10HolderPct:  (json['top10_holder_pct']   as num?)?.toDouble(),
      top1HolderPct:   (json['top1_holder_pct']    as num?)?.toDouble(),
      goplusRisk:      json['goplus_risk']         as bool? ?? false,
      hasTwitter:      json['has_twitter']         as bool? ?? false,
      hasTelegram:     json['has_telegram']        as bool? ?? false,
      hasWebsite:      json['has_website']         as bool? ?? false,
      imageUrl:        json['image_url']           as String?,
      score:           (json['score']              as num?)?.toDouble() ?? 0.0,
      scoreM:          (json['score_m']            as num?)?.toDouble() ?? 0.0,
      scoreQ:          (json['score_q']            as num?)?.toDouble() ?? 0.0,
      scoreP:          (json['score_p']            as num?)?.toDouble() ?? 0.0,
      recommendation:  json['recommendation']      as String? ?? 'normal',
      scannedAt:       json['scanned_at']          as String? ?? '',
    );
  }

  /// 1h 买卖比（买单占比，0~1）
  double get buySellRatio1h {
    final total = buys1h + sells1h;
    return total > 0 ? buys1h / total : 0.5;
  }

  /// 热度等级（基于综合分）
  String get heatLevel {
    if (score >= 72) return 'fire';   // 强推
    if (score >= 50) return 'hot';    // 普通
    if (score >= 30) return 'warm';
    return 'cool';
  }

  /// 链标签 & 颜色
  String get chainLabel {
    return switch (chain) {
      'solana' => 'SOL',
      'bsc'    => 'BSC',
      'base'   => 'BASE',
      'eth'    => 'ETH',
      _        => chain.toUpperCase(),
    };
  }
}
