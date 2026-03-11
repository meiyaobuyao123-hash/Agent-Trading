/// DexScreener 代币信息（社交链接 + 配对数据 + 多时间维度交易数据）
class DexScreenerInfo {
  final String? twitterUrl;
  final String? telegramUrl;
  final String? websiteUrl;
  final String? imageUrl;
  final String? description;
  final double? fdv;
  final double? marketCap;
  final String? pairCreatedAt;
  final List<DexPair> pairs;

  // ── 多时间维度实时数据 ──
  final DexTimeframeData? tfM5;
  final DexTimeframeData? tfH1;
  final DexTimeframeData? tfH6;
  final DexTimeframeData? tfH24;

  const DexScreenerInfo({
    this.twitterUrl,
    this.telegramUrl,
    this.websiteUrl,
    this.imageUrl,
    this.description,
    this.fdv,
    this.marketCap,
    this.pairCreatedAt,
    required this.pairs,
    this.tfM5,
    this.tfH1,
    this.tfH6,
    this.tfH24,
  });

  /// 根据 timeframe key 获取对应数据
  DexTimeframeData? getTimeframe(String tf) => switch (tf) {
    '5m' => tfM5,
    '1h' => tfH1,
    '4h' => tfH6, // DexScreener 没有 4h，用 6h 近似
    '24h' => tfH24,
    _ => tfH1,
  };

  factory DexScreenerInfo.fromJson(Map<String, dynamic> json) {
    final pairs = (json['pairs'] as List?)
            ?.map((p) => DexPair.fromJson(p as Map<String, dynamic>))
            .toList() ??
        [];

    String? twitter, telegram, website, image, description, pairCreatedAt;
    double? fdv, marketCap;
    DexTimeframeData? tfM5, tfH1, tfH6, tfH24;

    if (pairs.isNotEmpty) {
      final raw = json['pairs'] as List?;
      if (raw != null && raw.isNotEmpty) {
        final firstPair = raw[0] as Map<String, dynamic>;

        // ── 社交信息 ──
        final pairInfo = firstPair['info'] as Map<String, dynamic>?;
        if (pairInfo != null) {
          final socials = pairInfo['socials'] as List? ?? [];
          for (final s in socials) {
            final m = s as Map<String, dynamic>;
            final type = m['type'] as String? ?? '';
            final url = m['url'] as String? ?? '';
            if (type == 'twitter') twitter = url;
            if (type == 'telegram') telegram = url;
          }
          final websites = pairInfo['websites'] as List? ?? [];
          if (websites.isNotEmpty) {
            website = (websites[0] as Map<String, dynamic>)['url'] as String?;
          }
          image = pairInfo['imageUrl'] as String?;
          // 注意: info.header 是 banner 图片 URL，不是文字描述
          // DexScreener 没有文字描述字段，description 留空
        }

        // ── FDV / MarketCap / 创建时间 ──
        fdv = (firstPair['fdv'] as num?)?.toDouble();
        marketCap = (firstPair['marketCap'] as num?)?.toDouble();
        final rawCreated = firstPair['pairCreatedAt'];
        if (rawCreated != null) {
          pairCreatedAt = rawCreated.toString();
        }

        // ── 多时间维度交易数据 ──
        final txns = firstPair['txns'] as Map<String, dynamic>?;
        final volume = firstPair['volume'] as Map<String, dynamic>?;
        final priceChange = firstPair['priceChange'] as Map<String, dynamic>?;

        tfM5 = DexTimeframeData.fromMaps(
          txns: txns?['m5'] as Map<String, dynamic>?,
          volume: volume?['m5'],
          priceChange: priceChange?['m5'],
        );
        tfH1 = DexTimeframeData.fromMaps(
          txns: txns?['h1'] as Map<String, dynamic>?,
          volume: volume?['h1'],
          priceChange: priceChange?['h1'],
        );
        tfH6 = DexTimeframeData.fromMaps(
          txns: txns?['h6'] as Map<String, dynamic>?,
          volume: volume?['h6'],
          priceChange: priceChange?['h6'],
        );
        tfH24 = DexTimeframeData.fromMaps(
          txns: txns?['h24'] as Map<String, dynamic>?,
          volume: volume?['h24'],
          priceChange: priceChange?['h24'],
        );
      }
    }

    return DexScreenerInfo(
      twitterUrl: twitter,
      telegramUrl: telegram,
      websiteUrl: website,
      imageUrl: image,
      description: description,
      fdv: fdv,
      marketCap: marketCap,
      pairCreatedAt: pairCreatedAt,
      pairs: pairs,
      tfM5: tfM5,
      tfH1: tfH1,
      tfH6: tfH6,
      tfH24: tfH24,
    );
  }
}

/// 单个时间维度的交易数据
class DexTimeframeData {
  final int buys;
  final int sells;
  final double volume;
  final double priceChange;

  const DexTimeframeData({
    required this.buys,
    required this.sells,
    required this.volume,
    required this.priceChange,
  });

  int get totalTxns => buys + sells;
  double get buyRatio => totalTxns > 0 ? buys / totalTxns : 0.5;

  factory DexTimeframeData.fromMaps({
    Map<String, dynamic>? txns,
    dynamic volume,
    dynamic priceChange,
  }) {
    return DexTimeframeData(
      buys: (txns?['buys'] as num?)?.toInt() ?? 0,
      sells: (txns?['sells'] as num?)?.toInt() ?? 0,
      volume: (volume as num?)?.toDouble() ?? 0,
      priceChange: (priceChange as num?)?.toDouble() ?? 0,
    );
  }
}

class DexPair {
  final String pairAddress;
  final String dexId;
  final double priceUsd;
  final double volume24h;
  final double liquidity;

  const DexPair({
    required this.pairAddress,
    required this.dexId,
    required this.priceUsd,
    required this.volume24h,
    required this.liquidity,
  });

  factory DexPair.fromJson(Map<String, dynamic> json) {
    return DexPair(
      pairAddress: json['pairAddress'] as String? ?? '',
      dexId: json['dexId'] as String? ?? '',
      priceUsd: double.tryParse(json['priceUsd']?.toString() ?? '') ?? 0,
      volume24h: ((json['volume'] as Map?)?['h24'] as num?)?.toDouble() ?? 0,
      liquidity: ((json['liquidity'] as Map?)?['usd'] as num?)?.toDouble() ?? 0,
    );
  }
}
