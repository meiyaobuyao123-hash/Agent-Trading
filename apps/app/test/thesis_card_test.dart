// ThesisCard widget 测试 — W3 D3
// 引用 lib/widgets/agent/thesis_card.dart
// 引用 lib/models/thesis.dart
//
// 跑法:
//   cd apps/app
//   flutter test test/thesis_card_test.dart

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:aitrading_app/widgets/agent/thesis_card.dart';
import 'package:aitrading_app/models/thesis.dart';

Thesis _baseThesis({
  String level = 'L2',
  String direction = 'bullish',
  double conviction = 0.72,
  List<String>? risks,
  List<EvidenceItem>? evidence,
  List<SimilarCase>? cases,
  double? costUsd = 0.025,
  int? latencyMs = 4200,
}) {
  return Thesis(
    thesisId: 'demo-001',
    chain: 'solana',
    tokenAddress: 'TRUMPmGjJgGgqPZkMP9KrYwoRrsAtwHzuKbMHvYn3D9',
    tokenSymbol: 'TRUMP',
    level: level,
    direction: direction,
    conviction: conviction,
    entryZone: const EntryZone(low: 1.10, high: 1.20),
    stopLoss: 0.95,
    targetPrice: const [1.45, 1.80, 2.40],
    risks: risks ?? const ['流动性可能枯竭', '大户砸盘风险'],
    summary30w: '短期看涨,小仓位试水',
    evidence: evidence ?? [
      EvidenceItem(source: 'smart_money_signals', value: '+45000 USD', ts: DateTime(2026, 5, 1)),
    ],
    similarPastCases: cases ?? const [],
    costUsd: costUsd,
    latencyMs: latencyMs,
    ts: DateTime(2026, 5, 1),
  );
}

Widget _wrap(Widget child) => MaterialApp(home: Scaffold(body: SingleChildScrollView(child: child)));


void main() {
  group('ThesisCard 基本渲染', () {
    testWidgets('显示代币 symbol + chain + level', (tester) async {
      final t = _baseThesis();
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));

      expect(find.text('TRUMP'), findsOneWidget);
      expect(find.text('SOLANA'), findsOneWidget);
      expect(find.text('L2'), findsOneWidget);
    });

    testWidgets('bullish direction 显示中文+置信度', (tester) async {
      final t = _baseThesis(direction: 'bullish', conviction: 0.72);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));

      expect(find.text('看涨'), findsOneWidget);
      expect(find.text('置信 72%'), findsOneWidget);
    });

    testWidgets('bearish direction', (tester) async {
      final t = _baseThesis(direction: 'bearish');
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));
      expect(find.text('看跌'), findsOneWidget);
    });

    testWidgets('hold direction', (tester) async {
      final t = _baseThesis(direction: 'hold', conviction: 0.4);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));
      expect(find.text('观望'), findsOneWidget);
    });

    testWidgets('avoid direction', (tester) async {
      final t = _baseThesis(direction: 'avoid', conviction: 0.3);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));
      expect(find.text('回避'), findsOneWidget);
    });

    testWidgets('显示入场/止损/目标', (tester) async {
      await tester.pumpWidget(_wrap(ThesisCard(thesis: _baseThesis())));

      expect(find.text('入场'), findsOneWidget);
      expect(find.text('止损'), findsOneWidget);
      expect(find.text('目标'), findsOneWidget);
      expect(find.text('\$1.10-1.20'), findsOneWidget);
      expect(find.text('\$0.95'), findsOneWidget);
      expect(find.text('\$1.45+'), findsOneWidget); // 多个目标加 +
    });

    testWidgets('显示 summary', (tester) async {
      await tester.pumpWidget(_wrap(ThesisCard(thesis: _baseThesis())));
      expect(find.text('短期看涨,小仓位试水'), findsOneWidget);
    });

    testWidgets('风险列表显示所有项', (tester) async {
      final t = _baseThesis(risks: const ['流动性枯竭风险', '大户砸盘', '监管不确定性']);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));

      expect(find.text('风险'), findsOneWidget);
      expect(find.text('流动性枯竭风险'), findsOneWidget);
      expect(find.text('大户砸盘'), findsOneWidget);
      expect(find.text('监管不确定性'), findsOneWidget);
    });

    testWidgets('Evidence 折叠区显示 source 数', (tester) async {
      final t = _baseThesis(evidence: [
        EvidenceItem(source: 'smart_money', value: 'x', ts: DateTime(2026, 5, 1)),
        EvidenceItem(source: 'hot_coins', value: 'y', ts: DateTime(2026, 5, 1)),
      ]);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));
      expect(find.text('证据 (2)'), findsOneWidget);
    });

    testWidgets('SimilarPastCases 折叠区显示数量', (tester) async {
      final t = _baseThesis(cases: [
        SimilarCase(
          tokenSymbol: 'PEPE',
          occurredAt: DateTime(2026, 3, 15),
          outcome: 'win',
          similarity: 0.78,
        ),
      ]);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));
      expect(find.text('历史相似 (1)'), findsOneWidget);
    });

    testWidgets('Footer 显示 cost + latency', (tester) async {
      final t = _baseThesis(costUsd: 0.025, latencyMs: 4200);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));
      // cost 显示为 $0.025
      expect(find.textContaining('0.025'), findsOneWidget);
      // latency 显示为 4200ms
      expect(find.textContaining('4200ms'), findsOneWidget);
    });
  });

  group('低置信度警告', () {
    testWidgets('conviction < 0.5 显示红条', (tester) async {
      final t = _baseThesis(direction: 'hold', conviction: 0.4);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));
      expect(find.text('低置信度分析,建议小仓位试水或观望'), findsOneWidget);
    });

    testWidgets('conviction >= 0.5 不显示红条', (tester) async {
      final t = _baseThesis(conviction: 0.72);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));
      expect(find.text('低置信度分析,建议小仓位试水或观望'), findsNothing);
    });
  });

  group('折叠交互', () {
    testWidgets('点击 Evidence 展开后显示具体数据', (tester) async {
      final t = _baseThesis(evidence: [
        EvidenceItem(source: 'smart_money_signals', value: '+45000', ts: DateTime(2026, 5, 1)),
      ]);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));

      // 默认折叠状态:不应见 +45000
      expect(find.text('+45000'), findsNothing);

      // 点击 expansion tile 标题展开
      await tester.tap(find.text('证据 (1)'));
      await tester.pumpAndSettle();

      expect(find.text('+45000'), findsOneWidget);
    });

    testWidgets('点击 SimilarPastCases 展开后显示具体 case', (tester) async {
      final t = _baseThesis(cases: [
        SimilarCase(
          tokenSymbol: 'PEPE',
          occurredAt: DateTime(2026, 3, 15),
          outcome: 'win',
          similarity: 0.78,
        ),
      ]);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));

      expect(find.text('PEPE'), findsNothing);
      await tester.tap(find.text('历史相似 (1)'));
      await tester.pumpAndSettle();
      expect(find.text('PEPE'), findsOneWidget);
    });
  });

  group('边界场景', () {
    testWidgets('空 evidence 不渲染折叠区', (tester) async {
      final t = _baseThesis(evidence: const []);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));
      expect(find.textContaining('证据 ('), findsNothing);
    });

    testWidgets('空 similar_past_cases 不渲染折叠区', (tester) async {
      final t = _baseThesis(cases: const []);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));
      expect(find.textContaining('历史相似 ('), findsNothing);
    });

    testWidgets('cost/latency 都为 null 时不渲染 Footer', (tester) async {
      final t = _baseThesis(costUsd: null, latencyMs: null);
      await tester.pumpWidget(_wrap(ThesisCard(thesis: t)));
      // 没有 ms 文字
      expect(find.textContaining('ms'), findsNothing);
    });
  });
}
