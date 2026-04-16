import '../config/app_config.dart';
import '../models/smart_money_txn.dart';
import 'api_client.dart';

/// 聪明钱交易详情服务
/// 通过后端 /api/smart-money/txns API 获取单笔交易数据
class SmartMoneyService {
  static const _base = AppConfig.backendBaseUrl;

  /// 获取某代币的聪明钱单笔交易列表
  static Future<List<SmartMoneyTxn>> fetchTxns(
    String chain,
    String tokenAddress, {
    String? txType,
    int limit = 100,
  }) async {
    var url = '$_base/api/smart-money/txns/$chain/$tokenAddress?limit=$limit';
    if (txType != null) {
      url += '&tx_type=$txType';
    }
    final resp = await ApiClient.instance.get(url);
    if (resp == null) return [];
    final data = resp['data'];
    if (data == null) return [];
    return (data as List)
        .map((e) => SmartMoneyTxn.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
