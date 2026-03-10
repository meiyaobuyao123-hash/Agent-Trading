import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'theme/app_theme.dart';
import 'theme/app_colors.dart';
import 'screens/market/market_screen.dart';
import 'screens/agent/agent_screen.dart';
import 'screens/history/history_screen.dart';
import 'screens/profile/profile_screen.dart';

class PumpSignalApp extends StatelessWidget {
  const PumpSignalApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Pump Signal',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: const MainShell(),
    );
  }
}

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: CupertinoTabBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        activeColor: AppColors.primary,
        inactiveColor: AppColors.iconInactive,
        backgroundColor: AppColors.surface.withValues(alpha: 0.94),
        border: const Border(
          top: BorderSide(color: Color(0x4DC6C6C8), width: 0.33),
        ),
        iconSize: 24,
        height: 50,
        items: const [
          BottomNavigationBarItem(
            icon: Icon(CupertinoIcons.chart_bar_square),
            label: '行情',
          ),
          BottomNavigationBarItem(
            icon: Icon(CupertinoIcons.square_grid_2x2),
            label: 'Agent',
          ),
          BottomNavigationBarItem(
            icon: Icon(CupertinoIcons.clock),
            label: '历史',
          ),
          BottomNavigationBarItem(
            icon: Icon(CupertinoIcons.person),
            label: '我的',
          ),
        ],
      ),
    );
  }
}
