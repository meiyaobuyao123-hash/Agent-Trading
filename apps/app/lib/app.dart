import 'dart:ui';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'theme/app_theme.dart';
import 'theme/app_colors.dart';
import 'theme/gradients.dart';
import 'screens/market/market_screen.dart';
import 'screens/agent/agent_screen.dart';
import 'screens/history/history_screen.dart';
import 'screens/profile/profile_screen.dart';

// ══════════════════════════════════════════════════════════════
//  主题状态管理
// ══════════════════════════════════════════════════════════════
class ThemeNotifier extends ChangeNotifier {
  ThemeMode _mode = ThemeMode.dark; // 默认 Dark

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
  }

  @override
  void dispose() {
    themeNotifier.removeListener(_rebuild);
    super.dispose();
  }

  void _rebuild() => setState(() {});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Pump Signal',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: themeNotifier.mode,
      home: const MainShell(),
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
    MarketScreen(),
    AgentScreen(),
    HistoryScreen(),
    ProfileScreen(),
  ];

  static const _tabItems = [
    _TabItem(icon: CupertinoIcons.chart_bar_square, label: '行情'),
    _TabItem(icon: CupertinoIcons.square_grid_2x2, label: 'Agent'),
    _TabItem(icon: CupertinoIcons.clock, label: '历史'),
    _TabItem(icon: CupertinoIcons.person, label: '我的'),
  ];

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final bottomPadding = MediaQuery.of(context).padding.bottom;

    return Scaffold(
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
      bottomNavigationBar: _buildGlassTabBar(c, bottomPadding),
    );
  }

  Widget _buildGlassTabBar(AppColorScheme c, double bottomPadding) {
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
              children: List.generate(_tabItems.length, (i) {
                final item = _tabItems[i];
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
