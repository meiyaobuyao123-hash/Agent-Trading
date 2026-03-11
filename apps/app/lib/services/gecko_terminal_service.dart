import '../models/ohlcv_data.dart';
import 'api_client.dart';

/// GeckoTerminal API — K线 OHLCV + 交易记录
class GeckoTerminalService {
  static final GeckoTerminalService instance = GeckoTerminalService._();
  GeckoTerminalService._();

  static const _baseUrl = 'https://api.geckoterminal.com/api/v2';
  static const _headers = {'Accept': 'application/json;version=20230302'};

  /// 获取 K 线蜡烛数据
  /// [network]: solana | bsc | base
  /// [poolAddress]: pair/pool 地址
  /// [timeframe]: minute | hour | day
  /// [aggregate]: 1/5/15 (minute), 1/4/12 (hour), 1 (day)
  Future<List<OhlcvCandle>> fetchOhlcv({
    required String network,
    required String poolAddress,
    required String timeframe,
    int aggregate = 1,
    int limit = 100,
  }) async {
    final url = '$_baseUrl/networks/$network/pools/$poolAddress'
        '/ohlcv/$timeframe?aggregate=$aggregate&limit=$limit&currency=usd';

    final data = await ApiClient.instance.get(url, headers: _headers);
    if (data == null) return [];

    final attrs = (data['data'] as Map?)?['attributes'] as Map?;
    final list = attrs?['ohlcv_list'] as List? ?? [];

    return list.map((e) => OhlcvCandle.fromList(e as List)).toList();
  }

  /// 获取最近交易记录（V2）
  Future<List<Map<String, dynamic>>> fetchTrades({
    required String network,
    required String poolAddress,
    int limit = 50,
  }) async {
    final url =
        '$_baseUrl/networks/$network/pools/$poolAddress/trades?trade_volume_in_usd_greater_than=0';

    final data = await ApiClient.instance.get(url, headers: _headers);
    if (data == null) return [];

    final list = data['data'] as List? ?? [];
    return list.map((e) {
      final attrs = (e as Map)['attributes'] as Map<String, dynamic>? ?? {};
      return {
        'kind': attrs['kind'] ?? '',
        'volume_usd': double.tryParse(attrs['volume_in_usd']?.toString() ?? '') ?? 0.0,
        'price_usd': double.tryParse(attrs['price_to_in_usd']?.toString() ?? '') ?? 0.0,
        'from_amount': double.tryParse(attrs['from_token_amount']?.toString() ?? '') ?? 0.0,
        'to_amount': double.tryParse(attrs['to_token_amount']?.toString() ?? '') ?? 0.0,
        'timestamp': attrs['block_timestamp'] ?? '',
        'tx_hash': attrs['tx_hash'] ?? '',
        'maker': attrs['tx_from_address'] ?? '',
      };
    }).take(limit).toList();
  }
}
