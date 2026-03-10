import 'package:flutter/material.dart';
import 'theme/app_theme.dart';
import 'theme/app_colors.dart';
import 'screens/picks/picks_screen.dart';
import 'screens/hot/hot_screen.dart';
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
    PicksScreen(),
    HotScreen(),
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
      bottomNavigationBar: _buildNavBar(),
    );
  }

  Widget _buildNavBar() {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border(
          top: BorderSide(color: AppColors.divider, width: 0.5),
        ),
        boxShadow: [
          BoxShadow(
            color: AppColors.shadow,
            blurRadius: 12,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(
            children: [
              _NavItem(icon: Icons.bolt_rounded,                     label: '新币榜',  index: 0, current: _currentIndex, onTap: _onTap),
              _NavItem(icon: Icons.local_fire_department_rounded,    label: '热币榜',  index: 1, current: _currentIndex, onTap: _onTap),
              _NavItem(icon: Icons.smart_toy_outlined,               label: 'Agent',  index: 2, current: _currentIndex, onTap: _onTap),
              _NavItem(icon: Icons.history_rounded,                  label: '历史',   index: 3, current: _currentIndex, onTap: _onTap),
              _NavItem(icon: Icons.person_outline_rounded,           label: '我的',   index: 4, current: _currentIndex, onTap: _onTap),
            ],
          ),
        ),
      ),
    );
  }

  void _onTap(int i) => setState(() => _currentIndex = i);
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final int index;
  final int current;
  final ValueChanged<int> onTap;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.index,
    required this.current,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final active = index == current;
    return Expanded(
      child: GestureDetector(
        onTap: () => onTap(index),
        behavior: HitTestBehavior.opaque,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 22,
              color: active ? AppColors.primary : AppColors.iconInactive,
            ),
            const SizedBox(height: 3),
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                fontWeight: active ? FontWeight.w600 : FontWeight.w400,
                color: active ? AppColors.primary : AppColors.iconInactive,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
