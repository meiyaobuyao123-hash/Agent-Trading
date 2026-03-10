import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

/// 实时价格刷新服务 — 使用 DexScreener 批量获取代币最新价格
/// 每 3 秒轮询一次，仅更新价格和涨跌幅字段
class PriceTickerService {
  static final PriceTickerService instance = PriceTickerService._();
  PriceTickerService._();

  Timer? _timer;
  final _controller = StreamController<Map<String, PriceTick>>.broadcast();

  /// 价格更新流 — key 为 address (lowercase)
  Stream<Map<String, PriceTick>> get stream => _controller.stream;

  /// 当前正在追踪的代币地址列表
  List<String> _addresses = [];

  /// 启动实时刷新
  void start(List<String> addresses) {
    _addresses = addresses.map((a) => a.toLowerCase()).toList();
    _timer?.cancel();
    // 立即获取一次
    _fetchPrices();
    // 每 3 秒刷新
    _timer = Timer.periodic(const Duration(seconds: 3), (_) => _fetchPrices());
  }

  /// 更新追踪列表（不重启 timer）
  void updateAddresses(List<String> addresses) {
    _addresses = addresses.map((a) => a.toLowerCase()).toList();
  }

  /// 停止刷新
  void stop() {
    _timer?.cancel();
    _timer = null;
  }

  Future<void> _fetchPrices() async {
    if (_addresses.isEmpty) return;

    try {
      // DexScreener 支持批量查询（逗号分隔，最多 30 个）
      final batch = _addresses.take(30).join(',');
      final url = 'https://api.dexscreener.com/latest/dex/tokens/$batch';
      final resp = await http.get(Uri.parse(url)).timeout(const Duration(seconds: 8));

      if (resp.statusCode != 200) return;

      final data = json.decode(resp.body);
      final pairs = data['pairs'] as List? ?? [];

      final result = <String, PriceTick>{};

      for (final pair in pairs) {
        final baseToken = pair['baseToken'] as Map<String, dynamic>?;
        if (baseToken == null) continue;

        final addr = (baseToken['address'] as String? ?? '').toLowerCase();
        if (addr.isEmpty || result.containsKey(addr)) continue;

        final priceStr = pair['priceUsd'] as String? ?? '0';
        final priceChange = pair['priceChange'] as Map<String, dynamic>? ?? {};

        result[addr] = PriceTick(
          address: addr,
          priceUsd: double.tryParse(priceStr) ?? 0,
          priceChange1h: (priceChange['h1'] as num?)?.toDouble() ?? 0,
          priceChange6h: (priceChange['h6'] as num?)?.toDouble() ?? 0,
          priceChange24h: (priceChange['h24'] as num?)?.toDouble() ?? 0,
        );
      }

      if (result.isNotEmpty && !_controller.isClosed) {
        _controller.add(result);
      }
    } catch (_) {
      // 静默失败，下次重试
    }
  }

  void dispose() {
    _timer?.cancel();
    _controller.close();
  }
}

class PriceTick {
  final String address;
  final double priceUsd;
  final double priceChange1h;
  final double priceChange6h;
  final double priceChange24h;

  const PriceTick({
    required this.address,
    required this.priceUsd,
    required this.priceChange1h,
    required this.priceChange6h,
    required this.priceChange24h,
  });
}
