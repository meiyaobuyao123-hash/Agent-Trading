import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/smart_money_txn.dart';

/// 聪明钱交易详情服务
/// 直接查询 Supabase smart_money_txns 表获取单笔交易数据
class SmartMoneyService {
  static SupabaseClient get _db => Supabase.instance.client;

  /// 获取某代币的聪明钱单笔交易列表
  static Future<List<SmartMoneyTxn>> fetchTxns(
    String chain,
    String tokenAddress, {
    String? txType,
    int limit = 100,
  }) async {
    var query = _db
        .from('smart_money_txns')
        .select(
          'wallet_address, wallet_tier, tx_type, volume_usd, '
          'market_cap_at_tx, price_at_tx, tx_time',
        )
        .eq('chain', chain)
        .eq('token_address', tokenAddress);

    if (txType != null) {
      query = query.eq('tx_type', txType);
    }

    final res = await query
        .order('tx_time', ascending: false)
        .limit(limit);

    return (res as List)
        .map((e) => SmartMoneyTxn.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
