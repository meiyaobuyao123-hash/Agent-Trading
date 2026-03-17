import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 语言设置管理器
/// - null = 跟随系统
/// - Locale('zh') / Locale('en') / Locale('ja') / Locale('ko') = 手动选择
class LocaleProvider extends ChangeNotifier {
  static const _key = 'app_locale';

  Locale? _locale; // null = 跟随系统

  Locale? get locale => _locale;

  /// 支持的语言列表
  static const supportedLocales = [
    Locale('zh'),
    Locale('en'),
    Locale('ja'),
    Locale('ko'),
  ];

  /// 语言显示名称
  static String displayName(Locale? locale) {
    if (locale == null) return '跟随系统';
    return switch (locale.languageCode) {
      'zh' => '中文',
      'en' => 'English',
      'ja' => '日本語',
      'ko' => '한국어',
      _ => locale.languageCode,
    };
  }

  /// 从 SharedPreferences 加载保存的语言设置
  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    final code = prefs.getString(_key);
    if (code != null && code.isNotEmpty) {
      _locale = Locale(code);
    }
  }

  /// 设置语言
  /// - locale == null 表示跟随系统
  Future<void> setLocale(Locale? locale) async {
    _locale = locale;
    final prefs = await SharedPreferences.getInstance();
    if (locale == null) {
      await prefs.remove(_key);
    } else {
      await prefs.setString(_key, locale.languageCode);
    }
    notifyListeners();
  }
}

/// 全局语言通知器
final localeProvider = LocaleProvider();
