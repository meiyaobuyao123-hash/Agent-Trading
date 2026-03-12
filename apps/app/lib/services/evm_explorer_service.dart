import 'dart:convert';
import 'package:http/http.dart' as http;

/// EVM 链区块浏览器服务 — BSC/Base Top Holder 查询
class EvmExplorerService {
  static final EvmExplorerService instance = EvmExplorerService._();
  EvmExplorerService._();

  /// 获取 BSC/Base 代币 Top Holder 列表
  ///
  /// 返回 holder 列表，如果查询失败返回空列表
  Future<List<TokenHolder>> fetchTopHolders({
    required String chain,
    required String contractAddress,
    int limit = 20,
  }) async {
    try {
      String baseUrl;

      switch (chain.toLowerCase()) {
        case 'bsc':
          baseUrl = 'https://api.bscscan.com/api';
          break;
        case 'base':
          baseUrl = 'https://api.basescan.org/api';
          break;
        case 'eth':
          baseUrl = 'https://api.etherscan.io/api';
          break;
        default:
          return [];
      }

      final uri = Uri.parse(
        '$baseUrl?module=token&action=tokenholderlist'
        '&contractaddress=$contractAddress'
        '&page=1&offset=$limit',
      );

      final response = await http.get(uri).timeout(
        const Duration(seconds: 10),
      );

      if (response.statusCode != 200) return [];

      final data = json.decode(response.body) as Map<String, dynamic>;
      if (data['status'] != '1') return [];

      final result = data['result'] as List<dynamic>? ?? [];
      return result.map((h) {
        final holder = h as Map<String, dynamic>;
        return TokenHolder(
          address: holder['TokenHolderAddress'] as String? ?? '',
          quantity: double.tryParse(
                holder['TokenHolderQuantity']?.toString() ?? '0',
              ) ??
              0,
        );
      }).toList();
    } catch (e) {
      return [];
    }
  }

  /// 计算 Top 1% 持仓比例
  ///
  /// 获取 top N holder，计算他们占总供应量的百分比
  Future<double?> fetchTop1HolderPct({
    required String chain,
    required String contractAddress,
  }) async {
    final holders = await fetchTopHolders(
      chain: chain,
      contractAddress: contractAddress,
      limit: 10,
    );

    if (holders.isEmpty) return null;

    // Top 1 holder 的百分比（简化计算）
    final totalOfTop = holders.fold<double>(
      0,
      (sum, h) => sum + h.quantity,
    );
    if (totalOfTop <= 0) return null;

    // 返回 top 1 holder 占 top holders 总量的比例
    return holders.first.quantity / totalOfTop;
  }
}

class TokenHolder {
  final String address;
  final double quantity;

  const TokenHolder({
    required this.address,
    required this.quantity,
  });
}
