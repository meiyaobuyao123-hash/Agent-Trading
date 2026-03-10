import '../models/dexscreener_info.dart';
import 'api_client.dart';

/// DexScreener API — 代币信息 + 社交链接
class DexScreenerService {
  static final DexScreenerService instance = DexScreenerService._();
  DexScreenerService._();

  static const _baseUrl = 'https://api.dexscreener.com';

  /// 获取代币信息（配对 + 社交链接）
  Future<DexScreenerInfo?> fetchTokenInfo(String address) async {
    final url = '$_baseUrl/latest/dex/tokens/$address';
    final data = await ApiClient.instance.get(url);
    if (data == null) return null;
    return DexScreenerInfo.fromJson(data);
  }
}
