/// DexScreener 代币信息（社交链接 + 配对数据）
class DexScreenerInfo {
  final String? twitterUrl;
  final String? telegramUrl;
  final String? websiteUrl;
  final String? imageUrl;
  final List<DexPair> pairs;

  const DexScreenerInfo({
    this.twitterUrl,
    this.telegramUrl,
    this.websiteUrl,
    this.imageUrl,
    required this.pairs,
  });

  factory DexScreenerInfo.fromJson(Map<String, dynamic> json) {
    final pairs = (json['pairs'] as List?)
            ?.map((p) => DexPair.fromJson(p as Map<String, dynamic>))
            .toList() ??
        [];

    String? twitter, telegram, website, image;

    if (pairs.isNotEmpty) {
      final info = (pairs.first as DexPair);
      // 从第一个 pair 提取社交信息
      final raw = json['pairs'] as List?;
      if (raw != null && raw.isNotEmpty) {
        final firstPair = raw[0] as Map<String, dynamic>;
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
        }
      }
    }

    return DexScreenerInfo(
      twitterUrl: twitter,
      telegramUrl: telegram,
      websiteUrl: website,
      imageUrl: image,
      pairs: pairs,
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
      volume24h: (json['volume'] as Map?)?['h24'] as double? ?? 0,
      liquidity: (json['liquidity'] as Map?)?['usd'] as double? ?? 0,
    );
  }
}
