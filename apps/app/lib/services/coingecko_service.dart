import 'dart:convert';
import 'package:http/http.dart' as http;

/// CoinGecko API 服务 — 代币描述、ATH/ATL、最大供应量
class CoinGeckoService {
  static final CoinGeckoService instance = CoinGeckoService._();
  CoinGeckoService._();

  static const _baseUrl = 'https://api.coingecko.com/api/v3';

  /// 链名 → CoinGecko platform ID
  static String _platformId(String chain) {
    switch (chain.toLowerCase()) {
      case 'solana':
        return 'solana';
      case 'bsc':
        return 'binance-smart-chain';
      case 'base':
        return 'base';
      case 'eth':
      case 'ethereum':
        return 'ethereum';
      default:
        return chain;
    }
  }

  /// 通过合约地址获取代币补充信息
  ///
  /// 返回包含 description, ath, atl, maxSupply 等字段的 Map，
  /// 如果代币未被 CoinGecko 收录则返回 null（404 优雅降级）
  Future<CoinGeckoTokenInfo?> fetchTokenInfo({
    required String chain,
    required String address,
  }) async {
    try {
      final platform = _platformId(chain);
      final url = '$_baseUrl/coins/$platform/contract/$address';
      final response = await http.get(
        Uri.parse(url),
        headers: {'accept': 'application/json'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 404) return null; // 小币未收录
      if (response.statusCode == 429) return null; // 速率限制
      if (response.statusCode != 200) return null;

      final data = json.decode(response.body) as Map<String, dynamic>;
      return CoinGeckoTokenInfo.fromJson(data);
    } catch (e) {
      // 网络错误/超时/解析错误 → 优雅降级
      return null;
    }
  }
}

/// CoinGecko 代币补充信息
class CoinGeckoTokenInfo {
  final String? description;
  final double? ath;
  final String? athDate;
  final double? atl;
  final String? atlDate;
  final double? maxSupply;
  final double? totalSupply;
  final double? marketCap;
  final double? totalVolume;
  final String? imageUrl;

  const CoinGeckoTokenInfo({
    this.description,
    this.ath,
    this.athDate,
    this.atl,
    this.atlDate,
    this.maxSupply,
    this.totalSupply,
    this.marketCap,
    this.totalVolume,
    this.imageUrl,
  });

  factory CoinGeckoTokenInfo.fromJson(Map<String, dynamic> json) {
    final marketData = json['market_data'] as Map<String, dynamic>?;
    final desc = json['description'] as Map<String, dynamic>?;
    final image = json['image'] as Map<String, dynamic>?;

    // 清理 HTML 标签
    String? rawDesc = desc?['en'] as String?;
    if (rawDesc != null && rawDesc.isNotEmpty) {
      rawDesc = rawDesc.replaceAll(RegExp(r'<[^>]*>'), '').trim();
      if (rawDesc.length > 500) {
        rawDesc = '${rawDesc.substring(0, 500)}...';
      }
    }

    return CoinGeckoTokenInfo(
      description: rawDesc,
      ath: (marketData?['ath']?['usd'] as num?)?.toDouble(),
      athDate: marketData?['ath_date']?['usd'] as String?,
      atl: (marketData?['atl']?['usd'] as num?)?.toDouble(),
      atlDate: marketData?['atl_date']?['usd'] as String?,
      maxSupply: (marketData?['max_supply'] as num?)?.toDouble(),
      totalSupply: (marketData?['total_supply'] as num?)?.toDouble(),
      marketCap: (marketData?['market_cap']?['usd'] as num?)?.toDouble(),
      totalVolume: (marketData?['total_volume']?['usd'] as num?)?.toDouble(),
      imageUrl: image?['large'] as String? ?? image?['small'] as String?,
    );
  }
}
