import '../config/app_config.dart';
import '../models/pump_signal.dart';
import 'api_client.dart';

/// 实时 pump 信号服务 — 对接后端 /api/pump/signals
class PumpSignalService {
  static final PumpSignalService instance = PumpSignalService._();
  PumpSignalService._();

  static const _base = AppConfig.backendBaseUrl;

  /// 获取当前实时信号池
  Future<List<PumpSignal>> fetchSignals() async {
    final resp = await ApiClient.instance.get('$_base/api/pump/signals');
    if (resp == null) return [];
    final list = resp['signals'] as List<dynamic>? ?? [];
    return list
        .map((e) => PumpSignal.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
