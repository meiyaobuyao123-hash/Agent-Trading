// HitlApprovalPage widget 测试 — W3 D4
// 引用 lib/screens/agent/hitl_approval_page.dart
// 引用 lib/models/pending_approval.dart
//
// 跑法:
//   cd apps/app
//   flutter test test/hitl_approval_page_test.dart

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:aitrading_app/models/pending_approval.dart';
import 'package:aitrading_app/models/thesis.dart';
import 'package:aitrading_app/screens/agent/hitl_approval_page.dart';

PendingApproval _approval({
  String status = 'pending',
  Duration expiresIn = const Duration(minutes: 14, seconds: 30),
  double? amount = 250.0,
  String? symbol = 'TRUMP',
  List<String>? conditions,
}) {
  final now = DateTime.now();
  return PendingApproval(
    approvalId: 'mock-001',
    strategyId: 'strat-1',
    triggerConditionsMatched: conditions ?? const [
      '聪明钱净流入 > \$30000',
      '1h 涨幅 > 15%',
    ],
    thesisId: 'thesis-1',
    tokenSymbol: symbol,
    tokenAddress: 'TRUMPaddr',
    chain: 'solana',
    amountUsd: amount,
    status: status,
    createdAt: now.subtract(const Duration(minutes: 1)),
    expiresAt: now.add(expiresIn),
  );
}

Thesis _thesis() => Thesis(
      thesisId: 'demo-001',
      chain: 'solana',
      tokenAddress: 'TRUMPaddr',
      tokenSymbol: 'TRUMP',
      level: 'L2',
      direction: 'bullish',
      conviction: 0.72,
      entryZone: const EntryZone(low: 1.10, high: 1.20),
      stopLoss: 0.95,
      targetPrice: const [1.45, 1.80],
      risks: const ['风险1', '风险2'],
      summary30w: '短期看涨',
      ts: DateTime(2026, 5, 1),
    );

Widget _wrap(Widget child) => MaterialApp(home: child);


void main() {
  group('HitlApprovalPage 基本渲染', () {
    testWidgets('显示策略触发条件列表', (tester) async {
      final a = _approval();
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a)));
      await tester.pump();

      expect(find.text('HITL 审批'), findsOneWidget);
      expect(find.text('策略触发'), findsOneWidget);
      expect(find.text('聪明钱净流入 > \$30000'), findsOneWidget);
      expect(find.text('1h 涨幅 > 15%'), findsOneWidget);
    });

    testWidgets('显示代币 symbol + chain', (tester) async {
      final a = _approval(symbol: 'TRUMP');
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a)));
      await tester.pump();
      expect(find.text('TRUMP · SOLANA'), findsOneWidget);
    });

    testWidgets('显示金额(amount_usd)', (tester) async {
      final a = _approval(amount: 250.0);
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a)));
      await tester.pump();
      expect(find.text('\$250.00'), findsOneWidget);
      expect(find.text('USD'), findsOneWidget);
      expect(find.textContaining('真金交易'), findsOneWidget);
    });

    testWidgets('显示倒计时', (tester) async {
      final a = _approval(expiresIn: const Duration(minutes: 14, seconds: 30));
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a)));
      await tester.pump();
      // mm:ss 格式,接受 14:30 ± 1s
      final hasCountdown = find.byWidgetPredicate((w) {
        if (w is Text && (w.data ?? '').contains(':')) {
          return RegExp(r'^\d{2}:\d{2}$').hasMatch(w.data!);
        }
        return false;
      });
      expect(hasCountdown, findsOneWidget);
    });

    testWidgets('未过期时按钮可用', (tester) async {
      final a = _approval(expiresIn: const Duration(minutes: 5));
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a)));
      await tester.pump();

      // 拒绝 + 批准并签名 都可点
      expect(find.text('拒绝'), findsOneWidget);
      expect(find.text('批准并签名'), findsOneWidget);

      final approveBtn = tester.widget<FilledButton>(find.byType(FilledButton).first);
      expect(approveBtn.onPressed, isNotNull);
    });

    testWidgets('过期时显示已过期 + 按钮禁用', (tester) async {
      final a = _approval(expiresIn: const Duration(seconds: -10));
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a)));
      await tester.pump();

      expect(find.text('已过期'), findsWidgets);  // 倒计时 + 按钮 label
      final approveBtn = tester.widget<FilledButton>(find.byType(FilledButton).first);
      expect(approveBtn.onPressed, isNull);
      final rejectBtn = tester.widget<OutlinedButton>(find.byType(OutlinedButton).first);
      expect(rejectBtn.onPressed, isNull);
    });

    testWidgets('thesis 提供时嵌入 ThesisCard', (tester) async {
      final a = _approval();
      final t = _thesis();
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a, thesis: t)));
      await tester.pump();
      // ThesisCard 渲染:能看到 conviction 标签
      expect(find.textContaining('置信'), findsOneWidget);
    });

    testWidgets('thesis 不提供时不渲染 ThesisCard', (tester) async {
      final a = _approval();
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a)));
      await tester.pump();
      expect(find.textContaining('置信'), findsNothing);
    });

    testWidgets('点击拒绝弹出确认对话', (tester) async {
      final a = _approval();
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a)));
      await tester.pump();

      await tester.tap(find.text('拒绝'));
      await tester.pumpAndSettle();
      expect(find.text('拒绝此交易?'), findsOneWidget);
      expect(find.text('确认拒绝'), findsOneWidget);

      // 点取消关闭对话
      await tester.tap(find.text('取消'));
      await tester.pumpAndSettle();
      expect(find.text('拒绝此交易?'), findsNothing);
    });

    testWidgets('点击批准弹出签名输入框', (tester) async {
      final a = _approval();
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a)));
      await tester.pump();

      await tester.tap(find.text('批准并签名'));
      await tester.pumpAndSettle();
      expect(find.text('生物认证 + 钱包签名'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
    });
  });

  group('边界场景', () {
    testWidgets('空触发条件显示提示', (tester) async {
      final a = _approval(conditions: const []);
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a)));
      await tester.pump();
      expect(find.text('无具体触发条件'), findsOneWidget);
    });

    testWidgets('null amount 显示 \$0.00', (tester) async {
      final a = _approval(amount: null);
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a)));
      await tester.pump();
      expect(find.text('\$0.00'), findsOneWidget);
    });

    testWidgets('null tokenSymbol 不渲染徽章', (tester) async {
      final a = _approval(symbol: null);
      await tester.pumpWidget(_wrap(HitlApprovalPage(approval: a)));
      await tester.pump();
      expect(find.textContaining('SOLANA'), findsNothing);
    });
  });
}
