import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/smart_money_txn.dart';

/// 聪明钱交易详情服务
/// 调用后端 /api/smart-money/txns 端点获取单笔交易数据
class SmartMoneyService {
  static const _apiBase = 'http://localhost:8000';

  /// 获取某代币的聪明钱单笔交易列表 + 汇总统计
  static Future<({List<SmartMoneyTxn> txns, SmartMoneyTxnSummary summary})>
      fetchTxns(
    String chain,
    String tokenAddress, {
    String? txType,
    int limit = 100,
  }) async {
    final params = <String, String>{'limit': '$limit'};
    if (txType != null) params['tx_type'] = txType;

    final uri = Uri.parse(
      '$_apiBase/api/smart-money/txns/$chain/$tokenAddress',
    ).replace(queryParameters: params);

    final resp = await http.get(uri).timeout(const Duration(seconds: 10));
    if (resp.statusCode != 200) {
      throw Exception('Failed to load txns: ${resp.statusCode}');
    }

    final json = jsonDecode(resp.body) as Map<String, dynamic>;
    final data = (json['data'] as List? ?? [])
        .map((e) => SmartMoneyTxn.fromJson(e as Map<String, dynamic>))
        .toList();
    final summary = SmartMoneyTxnSummary.fromJson(
      json['summary'] as Map<String, dynamic>? ?? {},
    );

    return (txns: data, summary: summary);
  }
}
