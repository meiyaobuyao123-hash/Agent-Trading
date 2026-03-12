/// 聪明钱信号模型
/// 对应 Supabase `smart_money_signals` 表
/// 聚合多个聪明钱钱包对同一代币的买卖活动
class SmartMoneySignal {
  final String chain;
  final String tokenAddress;
  final String tokenName;
  final String tokenSymbol;

  // 买卖聚合
  final int buyCount;
  final int sellCount;
  final double buyVolume;
  final double sellVolume;
  final int uniqueBuyers;
  final int uniqueSellers;

  // 分层统计
  final int eliteBuyCount;
  final int eliteSellCount;
  final int verifiedBuyCount;
  final int verifiedSellCount;

  // 热度
  final double heatScore;
  final int netFlow;

  // 市场数据
  final double priceUsd;
  final double marketCapUsd;
  final double liquidityUsd;
  final double volume24hUsd;
  final double priceChange24h;
  final double priceChange1h;
  final String? imageUrl;
  final String? pairAddress;
  final String? dexId;

  // 时间
  final String? latestSignalAt;
  final String? scanTime;

  const SmartMoneySignal({
    required this.chain,
    required this.tokenAddress,
    this.tokenName = '',
    this.tokenSymbol = '',
    this.buyCount = 0,
    this.sellCount = 0,
    this.buyVolume = 0,
    this.sellVolume = 0,
    this.uniqueBuyers = 0,
    this.uniqueSellers = 0,
    this.eliteBuyCount = 0,
    this.eliteSellCount = 0,
    this.verifiedBuyCount = 0,
    this.verifiedSellCount = 0,
    this.heatScore = 0,
    this.netFlow = 0,
    this.priceUsd = 0,
    this.marketCapUsd = 0,
    this.liquidityUsd = 0,
    this.volume24hUsd = 0,
    this.priceChange24h = 0,
    this.priceChange1h = 0,
    this.imageUrl,
    this.pairAddress,
    this.dexId,
    this.latestSignalAt,
    this.scanTime,
  });

  factory SmartMoneySignal.fromJson(Map<String, dynamic> json) {
    return SmartMoneySignal(
      chain: json['chain'] as String? ?? '',
      tokenAddress: json['token_address'] as String? ?? '',
      tokenName: json['token_name'] as String? ?? '',
      tokenSymbol: json['token_symbol'] as String? ?? '',
      buyCount: (json['buy_count'] as num?)?.toInt() ?? 0,
      sellCount: (json['sell_count'] as num?)?.toInt() ?? 0,
      buyVolume: (json['buy_volume'] as num?)?.toDouble() ?? 0,
      sellVolume: (json['sell_volume'] as num?)?.toDouble() ?? 0,
      uniqueBuyers: (json['unique_buyers'] as num?)?.toInt() ?? 0,
      uniqueSellers: (json['unique_sellers'] as num?)?.toInt() ?? 0,
      eliteBuyCount: (json['elite_buy_count'] as num?)?.toInt() ?? 0,
      eliteSellCount: (json['elite_sell_count'] as num?)?.toInt() ?? 0,
      verifiedBuyCount: (json['verified_buy_count'] as num?)?.toInt() ?? 0,
      verifiedSellCount: (json['verified_sell_count'] as num?)?.toInt() ?? 0,
      heatScore: (json['heat_score'] as num?)?.toDouble() ?? 0,
      netFlow: (json['net_flow'] as num?)?.toInt() ?? 0,
      priceUsd: (json['price_usd'] as num?)?.toDouble() ?? 0,
      marketCapUsd: (json['market_cap_usd'] as num?)?.toDouble() ?? 0,
      liquidityUsd: (json['liquidity_usd'] as num?)?.toDouble() ?? 0,
      volume24hUsd: (json['volume_24h_usd'] as num?)?.toDouble() ?? 0,
      priceChange24h: (json['price_change_24h'] as num?)?.toDouble() ?? 0,
      priceChange1h: (json['price_change_1h'] as num?)?.toDouble() ?? 0,
      imageUrl: json['image_url'] as String?,
      pairAddress: json['pair_address'] as String?,
      dexId: json['dex_id'] as String?,
      latestSignalAt: json['latest_signal_at'] as String?,
      scanTime: json['scan_time'] as String?,
    );
  }

  /// 链标签
  String get chainLabel => switch (chain) {
    'solana' => 'SOL',
    'bsc' => 'BSC',
    'base' => 'BASE',
    'eth' => 'ETH',
    _ => chain.toUpperCase(),
  };

  /// 买入热度（买多于卖 = 看涨信号）
  bool get isBullish => buyCount > sellCount;

  /// 信号强度: strong / medium / weak
  String get signalStrength {
    if (eliteBuyCount >= 2 && netFlow >= 3) return 'strong';
    if (eliteBuyCount >= 1 || netFlow >= 2) return 'medium';
    return 'weak';
  }

  /// 时间显示
  String get timeAgo {
    if (latestSignalAt == null) return '';
    try {
      final dt = DateTime.parse(latestSignalAt!);
      final diff = DateTime.now().toUtc().difference(dt);
      if (diff.inMinutes < 60) return '${diff.inMinutes}m前';
      if (diff.inHours < 24) return '${diff.inHours}h前';
      return '${diff.inDays}d前';
    } catch (_) {
      return '';
    }
  }
}
