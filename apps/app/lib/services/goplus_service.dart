import '../models/goplus_report.dart';
import 'api_client.dart';

/// GoPlus 安全检测 API
class GoPlusService {
  static final GoPlusService instance = GoPlusService._();
  GoPlusService._();

  static const _baseUrl = 'https://api.gopluslabs.io/api/v1';

  /// 获取代币安全报告
  /// [chain]: solana | bsc | base
  /// [address]: 代币合约地址
  Future<GoPlusReport?> fetchReport({
    required String chain,
    required String address,
  }) async {
    final chainId = switch (chain) {
      'solana' => 'solana',
      'bsc' => '56',
      'base' => '8453',
      _ => chain,
    };

    final String url;
    if (chainId == 'solana') {
      url = '$_baseUrl/solana/token_security?contract_addresses=$address';
    } else {
      url = '$_baseUrl/token_security/$chainId?contract_addresses=$address';
    }

    final data = await ApiClient.instance.get(url);
    if (data == null) return null;

    final result = data['result'] as Map<String, dynamic>? ?? {};
    final addr = address.toLowerCase();
    final info = result[addr] as Map<String, dynamic>? ??
        result[address] as Map<String, dynamic>? ??
        (result.isNotEmpty ? result.values.first as Map<String, dynamic>? : null);

    if (info == null) return null;

    final isSol = chainId == 'solana';

    return GoPlusReport(
      isHoneypot: isSol
          ? (info['cannot_buy'] == '1')
          : (info['is_honeypot'] == '1'),
      isOpenSource: isSol ? true : (info['is_open_source'] == '1'),
      buyTax: _parsePct(info['buy_tax']),
      sellTax: _parsePct(info['sell_tax']),
      cannotSellAll: info['cannot_sell_all'] == '1',
      holderCount: int.tryParse(info['holder_count']?.toString() ?? '') ?? 0,
      top10HolderPct: _parsePct(info['top_10_holder_rate']),
    );
  }

  double _parsePct(dynamic v) {
    if (v == null) return 0;
    final d = double.tryParse(v.toString()) ?? 0;
    return d > 1 ? d : d * 100; // GoPlus 有时返回 0~1，有时返回百分比
  }
}
