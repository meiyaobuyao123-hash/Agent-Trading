import '../config/app_config.dart';
import '../models/hot_coin.dart';
import '../models/smart_money_signal.dart';
import 'api_client.dart';

class SupabaseService {
  static final SupabaseService instance = SupabaseService._();
  SupabaseService._();

  static const _base = AppConfig.backendBaseUrl;

  // ─────────────────────────────────────────────────
  // 热币榜：多链外盘热币（通过后端 /api/hot-coins）
  // 按综合分降序，强推优先，排除安全风险标记
  // ─────────────────────────────────────────────────
  Future<List<HotCoin>> fetchHotCoins({int limit = 50}) async {
    final resp = await ApiClient.instance.get(
      '$_base/api/hot-coins?limit=$limit',
    );
    if (resp == null) return [];
    final data = resp['data'];
    if (data == null) return [];
    return (data as List)
        .map((e) => HotCoin.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ─────────────────────────────────────────────────
  // 聪明钱信号：多链聪明钱买卖聚合（通过后端 /api/smart-money/signals）
  // ─────────────────────────────────────────────────
  Future<List<SmartMoneySignal>> fetchSmartMoneySignals({
    String? chain,
    int limit = 50,
    double minHeat = 0,
  }) async {
    var url = '$_base/api/smart-money/signals?limit=$limit&min_heat=$minHeat';
    if (chain != null) {
      url += '&chain=$chain';
    }
    final resp = await ApiClient.instance.get(url);
    if (resp == null) return [];
    final data = resp['data'];
    if (data == null) return [];
    return (data as List)
        .map((e) => SmartMoneySignal.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
