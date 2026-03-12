import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

/// 实时价格刷新服务 — OKX 优先（通过后端代理），DexScreener fallback
/// 每 1 秒轮询一次（OKX 价格毫秒级更新），仅更新价格和涨跌幅字段
/// OKX 数据源通过 FastAPI /api/price/batch 代理，避免客户端做 HMAC 签名
class PriceTickerService {
  static final PriceTickerService instance = PriceTickerService._();
  PriceTickerService._();

  Timer? _timer;
  final _controller = StreamController<Map<String, PriceTick>>.broadcast();

  /// 价格更新流 — key 为 address (lowercase)
  Stream<Map<String, PriceTick>> get stream => _controller.stream;

  /// 当前正在追踪的代币地址列表（按链分组）
  Map<String, List<String>> _chainAddresses = {};

  // TODO: 生产环境替换为实际部署地址
  static const _apiBase = 'http://localhost:8000';

  /// 启动实时刷新（单链，兼容旧接口）
  void start(List<String> addresses, {String chain = 'solana'}) {
    _chainAddresses = {chain: addresses.map((a) => a.toLowerCase()).toList()};
    _timer?.cancel();
    _fetchPrices();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) => _fetchPrices());
  }

  /// 启动多链实时刷新
  void startMultiChain(Map<String, List<String>> chainAddresses) {
    _chainAddresses = {};
    for (final entry in chainAddresses.entries) {
      _chainAddresses[entry.key] =
          entry.value.map((a) => a.toLowerCase()).toList();
    }
    _timer?.cancel();
    _fetchPrices();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) => _fetchPrices());
  }

  /// 更新追踪列表（不重启 timer）
  void updateAddresses(List<String> addresses, {String chain = 'solana'}) {
    _chainAddresses[chain] = addresses.map((a) => a.toLowerCase()).toList();
  }

  /// 停止刷新
  void stop() {
    _timer?.cancel();
    _timer = null;
  }

  Future<void> _fetchPrices() async {
    if (_chainAddresses.isEmpty) return;

    final result = <String, PriceTick>{};

    for (final entry in _chainAddresses.entries) {
      final chain = entry.key;
      final addresses = entry.value;
      if (addresses.isEmpty) continue;

      try {
        // OKX 每批最多 100 个
        final batch = addresses.take(100).join(',');
        final url = '$_apiBase/api/price/batch?chain=$chain&addresses=$batch';
        final resp = await http
            .get(Uri.parse(url))
            .timeout(const Duration(seconds: 8));

        if (resp.statusCode != 200) {
          // OKX 代理失败 → DexScreener fallback
          await _fetchDexScreenerFallback(addresses, result);
          continue;
        }

        final data = json.decode(resp.body) as Map<String, dynamic>;
        final priceData = data['data'] as Map<String, dynamic>? ?? {};

        for (final addr in addresses) {
          final info = priceData[addr] as Map<String, dynamic>?;
          if (info == null) continue;

          result[addr] = PriceTick(
            address: addr,
            priceUsd: (info['price'] as num?)?.toDouble() ?? 0,
            priceChange5m: (info['change5m'] as num?)?.toDouble() ?? 0,
            priceChange1h: (info['change1h'] as num?)?.toDouble() ?? 0,
            priceChange4h: (info['change4h'] as num?)?.toDouble() ?? 0,
            priceChange6h: 0,
            priceChange24h: (info['change24h'] as num?)?.toDouble() ?? 0,
          );
        }
      } catch (_) {
        // OKX 代理超时 → DexScreener fallback
        await _fetchDexScreenerFallback(addresses, result);
      }
    }

    if (result.isNotEmpty && !_controller.isClosed) {
      _controller.add(result);
    }
  }

  /// DexScreener fallback（当 OKX 后端不可用时）
  Future<void> _fetchDexScreenerFallback(
    List<String> addresses,
    Map<String, PriceTick> result,
  ) async {
    try {
      final batch = addresses.take(30).join(',');
      final url = 'https://api.dexscreener.com/latest/dex/tokens/$batch';
      final resp = await http
          .get(Uri.parse(url))
          .timeout(const Duration(seconds: 8));

      if (resp.statusCode != 200) return;

      final data = json.decode(resp.body);
      final pairs = data['pairs'] as List? ?? [];

      for (final pair in pairs) {
        final baseToken = pair['baseToken'] as Map<String, dynamic>?;
        if (baseToken == null) continue;

        final addr = (baseToken['address'] as String? ?? '').toLowerCase();
        if (addr.isEmpty || result.containsKey(addr)) continue;

        final priceStr = pair['priceUsd'] as String? ?? '0';
        final priceChange =
            pair['priceChange'] as Map<String, dynamic>? ?? {};

        result[addr] = PriceTick(
          address: addr,
          priceUsd: double.tryParse(priceStr) ?? 0,
          priceChange5m: (priceChange['m5'] as num?)?.toDouble() ?? 0,
          priceChange1h: (priceChange['h1'] as num?)?.toDouble() ?? 0,
          priceChange4h: (priceChange['h6'] as num?)?.toDouble() ?? 0, // DexScreener 无4h，用6h近似
          priceChange6h: (priceChange['h6'] as num?)?.toDouble() ?? 0,
          priceChange24h: (priceChange['h24'] as num?)?.toDouble() ?? 0,
        );
      }
    } catch (_) {
      // 静默失败
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
  final double priceChange5m;
  final double priceChange1h;
  final double priceChange4h;
  final double priceChange6h;
  final double priceChange24h;

  const PriceTick({
    required this.address,
    required this.priceUsd,
    this.priceChange5m = 0,
    required this.priceChange1h,
    this.priceChange4h = 0,
    this.priceChange6h = 0,
    required this.priceChange24h,
  });
}
