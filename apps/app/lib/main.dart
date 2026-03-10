import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'app.dart';

// ─── Supabase 配置 ────────────────────────────────────
// ⚠️ 将以下值替换为你的真实凭证（不要提交真实 key 到 Git）
// Supabase Dashboard → Project Settings → API
const _supabaseUrl = 'YOUR_SUPABASE_URL';
const _supabaseKey = 'YOUR_SUPABASE_ANON_KEY';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // 初始化 Supabase
  await Supabase.initialize(
    url: _supabaseUrl,
    anonKey: _supabaseKey,
  );

  // 状态栏透明沉浸式
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarBrightness: Brightness.dark,
      statusBarIconBrightness: Brightness.light,
    ),
  );

  // 锁定竖屏
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  runApp(const PumpSignalApp());
}
