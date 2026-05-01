// MemoryManagementPage widget tests
// 引用 lib/screens/agent/memory_management_page.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:aitrading_app/screens/agent/memory_management_page.dart';

void main() {
  group('MemoryManagementPage', () {
    testWidgets('shows AppBar title 我的规则与记忆', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: const MemoryManagementPage(),
        theme: ThemeData(useMaterial3: true, brightness: Brightness.dark),
      ));
      expect(find.text('我的规则与记忆'), findsOneWidget);
    });

    testWidgets('renders stats bar with status counts after load',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: const MemoryManagementPage(),
        theme: ThemeData(useMaterial3: true, brightness: Brightness.dark),
      ));
      for (int i = 0; i < 8; i++) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      expect(find.text('总规则'), findsOneWidget);
      expect(find.text('Active'), findsOneWidget);
      expect(find.text('Shadow'), findsOneWidget);
      expect(find.text('Dormant'), findsOneWidget);
    });

    testWidgets('renders mock rule cards with status badges', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: const MemoryManagementPage(),
        theme: ThemeData(useMaterial3: true, brightness: Brightness.dark),
      ));
      for (int i = 0; i < 8; i++) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      // 至少一个 ACTIVE 和一个 SHADOW(mock 数据)
      expect(find.text('ACTIVE'), findsWidgets);
      expect(find.text('SHADOW'), findsWidgets);
    });

    testWidgets('help icon opens bottom sheet with status legend',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: const MemoryManagementPage(),
        theme: ThemeData(useMaterial3: true, brightness: Brightness.dark),
      ));
      for (int i = 0; i < 8; i++) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      await tester.tap(find.byIcon(Icons.help_outline));
      await tester.pumpAndSettle();
      expect(find.text('规则状态说明'), findsOneWidget);
    });

    testWidgets('rule card has 启用/禁用/删除 buttons', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: const MemoryManagementPage(),
        theme: ThemeData(useMaterial3: true, brightness: Brightness.dark),
      ));
      for (int i = 0; i < 8; i++) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      expect(find.text('删除'), findsWidgets);
      // 至少一个 ACTIVE 规则会显示"禁用"
      expect(find.text('禁用'), findsWidgets);
    });
  });
}
