import '../config/app_config.dart';
import '../models/pump_signal.dart';
import 'api_client.dart';

/// 实时 pump 信号服务 — 对接后端 /api/pump/signals
class PumpSignalService {
  static final PumpSignalService instance = PumpSignalService._();
  PumpSignalService._();

  static const _base = AppConfig.backendBaseUrl;

  /// 获取当前实时信号池（含历史回退）
  /// 返回 (signals, isHistory)
  Future<({List<PumpSignal> signals, bool isHistory})> fetchSignals() async {
    final resp = await ApiClient.instance.get('$_base/api/pump/signals');
    if (resp == null) return (signals: <PumpSignal>[], isHistory: false);
    final list = resp['signals'] as List<dynamic>? ?? [];
    final isHistory = resp['is_history'] as bool? ?? false;
    return (
      signals: list
          .map((e) => PumpSignal.fromJson(e as Map<String, dynamic>))
          .toList(),
      isHistory: isHistory,
    );
  }
}
