// DeepLinkRouter 单元测试 — 测路由逻辑(避开真实页面的 http 调用)
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:aitrading_app/services/deep_link_router.dart';

void main() {
  group('DeepLinkRouter unit (no nav)', () {
    test('non-aitrading scheme returns false', () async {
      final ok = await DeepLinkRouter.handle('https://example.com');
      expect(ok, isFalse);
    });

    test('handleFromPushData with empty deep_link returns false', () async {
      final ok = await DeepLinkRouter.handleFromPushData({});
      expect(ok, isFalse);
    });

    test('handleFromPushData with non-string deep_link returns false', () async {
      final ok = await DeepLinkRouter.handleFromPushData({'deep_link': 123});
      expect(ok, isFalse);
    });

    test('handle without navigator returns false (graceful)', () async {
      // navigatorKey 还没挂到 widget tree
      final ok = await DeepLinkRouter.handle('aitrading://review/daily');
      expect(ok, isFalse);
    });
  });

  group('DeepLinkRouter nav (with navigatorKey)', () {
    testWidgets('aitrading://home pops to root', (tester) async {
      await tester.pumpWidget(MaterialApp(
        navigatorKey: DeepLinkRouter.navigatorKey,
        home: const Scaffold(body: Text('root')),
      ));
      // 推一个新页面
      DeepLinkRouter.navigatorKey.currentState!.push(
        MaterialPageRoute(
          builder: (_) => const Scaffold(body: Text('pushed')),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('pushed'), findsOneWidget);
      // home 应该 pop 回 root
      final ok = await DeepLinkRouter.handle('aitrading://home');
      await tester.pumpAndSettle();
      expect(ok, isTrue);
      expect(find.text('root'), findsOneWidget);
    });

    testWidgets('unknown path falls to home', (tester) async {
      await tester.pumpWidget(MaterialApp(
        navigatorKey: DeepLinkRouter.navigatorKey,
        home: const Scaffold(body: Text('root')),
      ));
      final ok = await DeepLinkRouter.handle('aitrading://nonexistent');
      await tester.pumpAndSettle();
      expect(ok, isTrue); // 因为 home 路径
      expect(find.text('root'), findsOneWidget);
    });

    testWidgets('handleFromPushData with valid deep_link routes',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        navigatorKey: DeepLinkRouter.navigatorKey,
        home: const Scaffold(body: Text('root')),
      ));
      // home 路由 → ok
      final ok = await DeepLinkRouter.handleFromPushData({
        'deep_link': 'aitrading://home',
      });
      await tester.pumpAndSettle();
      expect(ok, isTrue);
    });
  });
}
