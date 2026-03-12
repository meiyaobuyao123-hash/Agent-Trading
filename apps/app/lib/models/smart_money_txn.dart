/// 聪明钱单笔交易模型
/// 对应后端 smart_money_txns 表 + summary 统计
class SmartMoneyTxn {
  final String walletAddress;
  final String walletTier; // elite, verified, watching
  final String txType; // buy, sell
  final double volumeUsd;
  final double marketCapAtTx;
  final double priceAtTx;
  final String txTime;

  const SmartMoneyTxn({
    required this.walletAddress,
    required this.walletTier,
    required this.txType,
    this.volumeUsd = 0,
    this.marketCapAtTx = 0,
    this.priceAtTx = 0,
    required this.txTime,
  });

  factory SmartMoneyTxn.fromJson(Map<String, dynamic> json) {
    return SmartMoneyTxn(
      walletAddress: json['wallet_address'] as String? ?? '',
      walletTier: json['wallet_tier'] as String? ?? 'watching',
      txType: json['tx_type'] as String? ?? 'buy',
      volumeUsd: (json['volume_usd'] as num?)?.toDouble() ?? 0,
      marketCapAtTx: (json['market_cap_at_tx'] as num?)?.toDouble() ?? 0,
      priceAtTx: (json['price_at_tx'] as num?)?.toDouble() ?? 0,
      txTime: json['tx_time'] as String? ?? '',
    );
  }

  bool get isBuy => txType == 'buy';

  /// 缩写钱包地址: 前6+...+后4
  String get walletShort {
    if (walletAddress.length < 12) return walletAddress;
    return '${walletAddress.substring(0, 6)}...${walletAddress.substring(walletAddress.length - 4)}';
  }

  /// 时间显示
  String get timeAgo {
    if (txTime.isEmpty) return '';
    try {
      final dt = DateTime.parse(txTime);
      final diff = DateTime.now().toUtc().difference(dt);
      if (diff.inMinutes < 1) return '刚刚';
      if (diff.inMinutes < 60) return '${diff.inMinutes}m前';
      if (diff.inHours < 24) return '${diff.inHours}h前';
      return '${diff.inDays}d前';
    } catch (_) {
      return '';
    }
  }

  /// tier 中文标签
  String get tierLabel => switch (walletTier) {
    'elite' => '精英',
    'verified' => '认证',
    _ => '关注',
  };
}

/// 汇总统计
class SmartMoneyTxnSummary {
  final double totalInflow;
  final double totalOutflow;
  final double netFlow;
  final int uniqueBuyers;
  final int uniqueSellers;
  final int buyCount;
  final int sellCount;

  const SmartMoneyTxnSummary({
    this.totalInflow = 0,
    this.totalOutflow = 0,
    this.netFlow = 0,
    this.uniqueBuyers = 0,
    this.uniqueSellers = 0,
    this.buyCount = 0,
    this.sellCount = 0,
  });

  factory SmartMoneyTxnSummary.fromJson(Map<String, dynamic> json) {
    return SmartMoneyTxnSummary(
      totalInflow: (json['total_inflow'] as num?)?.toDouble() ?? 0,
      totalOutflow: (json['total_outflow'] as num?)?.toDouble() ?? 0,
      netFlow: (json['net_flow'] as num?)?.toDouble() ?? 0,
      uniqueBuyers: (json['unique_buyers'] as num?)?.toInt() ?? 0,
      uniqueSellers: (json['unique_sellers'] as num?)?.toInt() ?? 0,
      buyCount: (json['buy_count'] as num?)?.toInt() ?? 0,
      sellCount: (json['sell_count'] as num?)?.toInt() ?? 0,
    );
  }

  bool get isNetPositive => netFlow > 0;
}
