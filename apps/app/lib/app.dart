import 'dart:ui';
import 'package:flutter/cupertino.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'l10n/app_localizations.dart';
import 'providers/locale_provider.dart';
import 'theme/app_theme.dart';
import 'theme/app_colors.dart';
import 'theme/gradients.dart';
import 'screens/data/data_screen.dart';
import 'screens/market/market_screen.dart';
import 'screens/agent/agent_screen.dart';
import 'screens/history/history_screen.dart';
import 'screens/profile/profile_screen.dart';
import 'screens/disclaimer/disclaimer_page.dart';

// ══════════════════════════════════════════════════════════════
//  主题状态管理
// ══════════════════════════════════════════════════════════════
class ThemeNotifier extends ChangeNotifier {
  ThemeMode _mode = ThemeMode.light; // 默认 Light

  ThemeMode get mode => _mode;

  void setMode(ThemeMode mode) {
    if (_mode != mode) {
      _mode = mode;
      notifyListeners();
    }
  }

  void toggle() {
    _mode = _mode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    notifyListeners();
  }
}

/// 全局主题通知器 — 可从 ProfileScreen 中切换
final themeNotifier = ThemeNotifier();

// ══════════════════════════════════════════════════════════════
//  App 入口
// ══════════════════════════════════════════════════════════════
class PumpSignalApp extends StatefulWidget {
  const PumpSignalApp({super.key});

  @override
  State<PumpSignalApp> createState() => _PumpSignalAppState();
}

class _PumpSignalAppState extends State<PumpSignalApp> {
  @override
  void initState() {
    super.initState();
    themeNotifier.addListener(_rebuild);
    localeProvider.addListener(_rebuild);
  }

  @override
  void dispose() {
    themeNotifier.removeListener(_rebuild);
    localeProvider.removeListener(_rebuild);
    super.dispose();
  }

  void _rebuild() => setState(() {});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI Trading',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: themeNotifier.mode,
      // i18n
      localizationsDelegates: S.localizationsDelegates,
      supportedLocales: S.supportedLocales,
      locale: localeProvider.locale, // null = 跟随系统
      localeResolutionCallback: (deviceLocale, supportedLocales) {
        for (final locale in supportedLocales) {
          if (locale.languageCode == deviceLocale?.languageCode) {
            return locale;
          }
        }
        return const Locale('en'); // 显式回退到英文
      },
      home: const _DisclaimerGate(),
    );
  }
}

// ══════════════════════════════════════════════════════════════
//  免责声明门禁 — 首次启动必须接受
// ══════════════════════════════════════════════════════════════
class _DisclaimerGate extends StatefulWidget {
  const _DisclaimerGate();

  @override
  State<_DisclaimerGate> createState() => _DisclaimerGateState();
}

class _DisclaimerGateState extends State<_DisclaimerGate> {
  bool _accepted = false;
  bool _checked = false;

  @override
  void initState() {
    super.initState();
    _checkDisclaimer();
  }

  Future<void> _checkDisclaimer() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final accepted = prefs.getBool('app_global_disclaimer_v1') ?? false;
      if (mounted) {
        setState(() {
          _accepted = accepted;
          _checked = true;
        });
      }
    } catch (e) {
      debugPrint('[DisclaimerGate] SharedPreferences error: $e');
      if (mounted) {
        setState(() {
          _accepted = false;
          _checked = true;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // 未检查完毕前显示空白过渡
    if (!_checked) {
      return const Scaffold(backgroundColor: Colors.black);
    }
    if (_accepted) {
      return const MainShell();
    }
    return DisclaimerPage(
      onAccepted: () => setState(() => _accepted = true),
    );
  }
}

// ══════════════════════════════════════════════════════════════
//  主壳 — 浮动毛玻璃 Tab Bar
// ══════════════════════════════════════════════════════════════
class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _currentIndex = 0;

  static const _screens = [
    DataScreen(),
    MarketScreen(),
    AgentScreen(),
    HistoryScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final bottomPadding = MediaQuery.of(context).padding.bottom;
    final t = S.of(context);

    final tabItems = [
      _TabItem(icon: CupertinoIcons.graph_square, label: '数据'),
      _TabItem(icon: CupertinoIcons.chart_bar_square, label: t.tabMarket),
      _TabItem(icon: CupertinoIcons.square_grid_2x2, label: t.tabAgent),
      _TabItem(icon: CupertinoIcons.clock, label: t.tabHistory),
      _TabItem(icon: CupertinoIcons.person, label: t.tabProfile),
    ];

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(
        systemNavigationBarColor: c.bg,
        systemNavigationBarIconBrightness: Brightness.light,
      ),
      child: Scaffold(
      backgroundColor: c.bg,
      extendBody: true, // 内容滚动到 Tab Bar 下方
      body: Stack(
        children: [
          // 渐变背景
          Positioned.fill(
            child: Container(decoration: AppGradients.screenBg(context)),
          ),
          // 极光光斑
          ...AppGradients.auroraSpots(context),
          // 屏幕内容
          Positioned.fill(
            child: IndexedStack(
              index: _currentIndex,
              children: _screens,
            ),
          ),
        ],
      ),
      bottomNavigationBar: _buildGlassTabBar(c, bottomPadding, tabItems),
    ),
    );
  }

  Widget _buildGlassTabBar(AppColorScheme c, double bottomPadding, List<_TabItem> tabItems) {
    return Container(
      margin: EdgeInsets.only(
        left: 16,
        right: 16,
        bottom: bottomPadding + 8,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(28),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 24, sigmaY: 24),
          child: Container(
            height: 64,
            decoration: BoxDecoration(
              color: c.cardGlass,
              borderRadius: BorderRadius.circular(28),
              border: Border.all(color: c.glassBorder, width: 1.0),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.06),
                  blurRadius: 20,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: List.generate(tabItems.length, (i) {
                final item = tabItems[i];
                final isActive = i == _currentIndex;
                return _buildTabItem(c, item, isActive, () {
                  setState(() => _currentIndex = i);
                });
              }),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTabItem(
    AppColorScheme c,
    _TabItem item,
    bool isActive,
    VoidCallback onTap,
  ) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOutCubic,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: isActive
            ? BoxDecoration(
                color: c.primary.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(20),
              )
            : null,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 200),
              child: Icon(
                item.icon,
                key: ValueKey('${item.label}_$isActive'),
                size: isActive ? 22 : 20,
                color: isActive ? c.primary : c.iconInactive,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              item.label,
              style: TextStyle(
                fontSize: 10,
                fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
                color: isActive ? c.primary : c.iconInactive,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TabItem {
  final IconData icon;
  final String label;
  const _TabItem({required this.icon, required this.label});
}
