import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'app.dart';

// ─── Supabase 配置 ────────────────────────────────────
const _supabaseUrl = 'https://qmzsruqgwaqusywprxlj.supabase.co';
const _supabaseKey = 'sb_publishable_2uL576o81fhTTuXxhTv20w_oKzjlLkS';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // 初始化 Supabase
  await Supabase.initialize(
    url: _supabaseUrl,
    anonKey: _supabaseKey,
  );

  // 锁定竖屏
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // 捕获详细错误信息
  FlutterError.onError = (details) {
    FlutterError.presentError(details);
    debugPrint('FLUTTER ERROR: ${details.exception}');
    debugPrint('${details.stack}');
  };

  runApp(const PumpSignalApp());
}
