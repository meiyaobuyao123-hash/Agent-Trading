// ReviewPage widget tests
// 引用 lib/screens/agent/review_page.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:aitrading_app/screens/agent/review_page.dart';

void main() {
  group('ReviewPage', () {
    testWidgets('renders period switcher with 日/周/月', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: const ReviewPage(),
        theme: ThemeData(useMaterial3: true, brightness: Brightness.dark),
      ));
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.text('日'), findsOneWidget);
      expect(find.text('周'), findsOneWidget);
      expect(find.text('月'), findsOneWidget);
    });

    testWidgets('shows AppBar with 复盘报告 title', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: const ReviewPage(),
        theme: ThemeData(useMaterial3: true, brightness: Brightness.dark),
      ));
      expect(find.text('复盘报告'), findsOneWidget);
    });

    testWidgets('renders mock review summary headline after load',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: const ReviewPage(),
        theme: ThemeData(useMaterial3: true, brightness: Brightness.dark),
      ));
      // mock loads via Future, give it 3 frames
      for (int i = 0; i < 8; i++) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      // Daily mock 标题
      expect(find.textContaining('胜率'), findsWidgets);
    });

    testWidgets('shows insights section header after load', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: const ReviewPage(),
        theme: ThemeData(useMaterial3: true, brightness: Brightness.dark),
      ));
      for (int i = 0; i < 8; i++) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      expect(find.textContaining('洞察'), findsWidgets);
    });

    testWidgets('shows manage memory button', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: const ReviewPage(),
        theme: ThemeData(useMaterial3: true, brightness: Brightness.dark),
      ));
      for (int i = 0; i < 8; i++) {
        await tester.pump(const Duration(milliseconds: 200));
      }
      // Scroll to bottom to reveal button
      await tester.drag(find.byType(ListView), const Offset(0, -1500));
      await tester.pump();
      expect(find.text('管理我的规则与记忆'), findsOneWidget);
    });
  });
}
