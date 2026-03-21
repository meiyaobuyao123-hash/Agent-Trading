import 'package:flutter/foundation.dart';
import 'api_client.dart';
import '../models/btc_eth.dart';

/// BTC/ETH 投资 Agent API 服务
class BtcEthService {
  static final BtcEthService instance = BtcEthService._();
  BtcEthService._();

  final _api = ApiClient.instance;

  /// 获取仪表盘数据
  Future<BtcEthDashboard?> fetchDashboard() async {
    try {
      final data = await _api.get('/api/btc-eth/dashboard');
      if (data != null) return BtcEthDashboard.fromJson(data);
    } catch (e) {
      debugPrint('[BtcEthService] dashboard: $e');
    }
    return null;
  }

  /// 获取交易信号
  Future<List<BtcEthSignal>> fetchSignals({String? asset, int limit = 20}) async {
    try {
      String path = '/api/btc-eth/signals?limit=$limit';
      if (asset != null) path += '&asset=$asset';
      final data = await _api.get(path);
      if (data != null) {
        final list = data['signals'] as List<dynamic>? ?? [];
        return list.map((j) => BtcEthSignal.fromJson(j as Map<String, dynamic>)).toList();
      }
    } catch (e) {
      debugPrint('[BtcEthService] signals: $e');
    }
    return [];
  }

  /// 获取风险预警
  Future<List<BtcEthAlert>> fetchAlerts() async {
    try {
      final data = await _api.get('/api/btc-eth/alerts');
      if (data != null) {
        final list = data['alerts'] as List<dynamic>? ?? [];
        return list.map((j) => BtcEthAlert.fromJson(j as Map<String, dynamic>)).toList();
      }
    } catch (e) {
      debugPrint('[BtcEthService] alerts: $e');
    }
    return [];
  }

  /// 获取最新周期报告
  Future<BtcEthReport?> fetchLatestReport(String asset) async {
    try {
      final data = await _api.get('/api/btc-eth/reports/$asset/latest');
      if (data != null && data['error'] == null) {
        return BtcEthReport.fromJson(data);
      }
    } catch (e) {
      debugPrint('[BtcEthService] report: $e');
    }
    return null;
  }

  /// 获取指标数据
  Future<Map<String, dynamic>?> fetchIndicators(String asset) async {
    try {
      return await _api.get('/api/btc-eth/indicators/$asset');
    } catch (e) {
      debugPrint('[BtcEthService] indicators: $e');
    }
    return null;
  }

  /// 获取健康状态
  Future<Map<String, dynamic>?> fetchHealth() async {
    try {
      return await _api.get('/api/btc-eth/health');
    } catch (e) {
      debugPrint('[BtcEthService] health: $e');
    }
    return null;
  }
}
