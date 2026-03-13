import 'api_client.dart';

/// Helius RPC — SOL 链专属（Top 持仓查询）
class HeliusService {
  static final HeliusService instance = HeliusService._();
  HeliusService._();

  static String get _rpcUrl {
    const key = String.fromEnvironment(
      'HELIUS_API_KEY',
      defaultValue: '22d3b20a-e69a-4532-854e-7e53dff3d1f6',
    );
    return 'https://mainnet.helius-rpc.com/?api-key=$key';
  }

  /// 获取 SOL 代币 Top1 持仓占比
  /// 返回 0~100 的百分比，失败返回 null
  Future<double?> fetchTop1HolderPct(String mintAddress) async {
    // 并行请求 supply + largest accounts
    final supplyResp = await ApiClient.instance.post(_rpcUrl, body: {
      'jsonrpc': '2.0',
      'id': 1,
      'method': 'getTokenSupply',
      'params': [mintAddress],
    });

    final holdersResp = await ApiClient.instance.post(_rpcUrl, body: {
      'jsonrpc': '2.0',
      'id': 2,
      'method': 'getTokenLargestAccounts',
      'params': [
        mintAddress,
        {'commitment': 'confirmed'}
      ],
    });

    if (supplyResp == null || holdersResp == null) return null;

    final supplyValue = supplyResp['result']?['value'] as Map?;
    final totalStr = supplyValue?['amount'] as String?;
    if (totalStr == null) return null;
    final total = double.tryParse(totalStr) ?? 0;
    if (total <= 0) return null;

    final accounts =
        (holdersResp['result']?['value'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    if (accounts.isEmpty) return null;

    final top1Str = accounts[0]['amount'] as String? ?? '0';
    final top1 = double.tryParse(top1Str) ?? 0;

    return (top1 / total) * 100;
  }

  /// 获取 SOL 代币 Top20 持仓账户（V2 用）
  Future<List<Map<String, dynamic>>> fetchLargestHolders(String mintAddress) async {
    final resp = await ApiClient.instance.post(_rpcUrl, body: {
      'jsonrpc': '2.0',
      'id': 1,
      'method': 'getTokenLargestAccounts',
      'params': [
        mintAddress,
        {'commitment': 'confirmed'}
      ],
    });

    if (resp == null) return [];

    final accounts =
        (resp['result']?['value'] as List?)?.cast<Map<String, dynamic>>() ?? [];

    final supplyResp = await ApiClient.instance.post(_rpcUrl, body: {
      'jsonrpc': '2.0',
      'id': 2,
      'method': 'getTokenSupply',
      'params': [mintAddress],
    });

    final totalStr = supplyResp?['result']?['value']?['amount'] as String? ?? '0';
    final total = double.tryParse(totalStr) ?? 1;

    return accounts.map((a) {
      final amount = double.tryParse(a['amount']?.toString() ?? '0') ?? 0;
      return {
        'address': a['address'] ?? '',
        'amount': amount,
        'pct': total > 0 ? (amount / total) * 100 : 0.0,
      };
    }).toList();
  }
}
