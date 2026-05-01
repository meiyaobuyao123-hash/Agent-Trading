// CocreationStepper widget tests
// 引用 lib/widgets/agent/cocreation_stepper.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:aitrading_app/widgets/agent/cocreation_stepper.dart';

Widget _wrap(Widget w) => MaterialApp(
      home: Scaffold(body: w),
      theme: ThemeData(useMaterial3: true, brightness: Brightness.dark),
    );

void main() {
  group('CocreationStepper', () {
    testWidgets('renders all 7 stages', (tester) async {
      await tester.pumpWidget(
        _wrap(const CocreationStepper(current: CocreationStage.idle)),
      );
      // 标签
      expect(find.text('开始'), findsOneWidget);
      expect(find.text('澄清'), findsOneWidget);
      expect(find.text('草案'), findsOneWidget);
      expect(find.text('Dry-run'), findsOneWidget);
      expect(find.text('微调'), findsOneWidget);
      expect(find.text('确认'), findsOneWidget);
      expect(find.text('保存'), findsOneWidget);
    });

    testWidgets('shows current stage hint', (tester) async {
      await tester.pumpWidget(
        _wrap(const CocreationStepper(current: CocreationStage.clarifying)),
      );
      expect(find.textContaining('Agent 正在澄清细节'), findsOneWidget);
    });

    testWidgets('shows step counter X / 7', (tester) async {
      await tester.pumpWidget(
        _wrap(const CocreationStepper(current: CocreationStage.draft)),
      );
      // draft 是第 3 (idx=2),显示 3 / 7
      expect(find.text('3 / 7'), findsOneWidget);
    });

    testWidgets('saved stage shows saved hint', (tester) async {
      await tester.pumpWidget(
        _wrap(const CocreationStepper(current: CocreationStage.saved)),
      );
      expect(find.textContaining('策略已保存'), findsOneWidget);
      expect(find.text('7 / 7'), findsOneWidget);
    });

    testWidgets('collapsed mode hides hint', (tester) async {
      await tester.pumpWidget(
        _wrap(const CocreationStepper(
          current: CocreationStage.draft,
          collapsed: true,
        )),
      );
      expect(find.textContaining('Agent 在写草案'), findsNothing);
    });

    testWidgets('stage extension exposes correct index', (tester) async {
      expect(CocreationStage.idle.index, 0);
      expect(CocreationStage.draft.index, 2);
      expect(CocreationStage.saved.index, 6);
    });

    testWidgets('hint never empty for any stage', (tester) async {
      for (final s in CocreationStage.values) {
        expect(s.hint.isNotEmpty, isTrue, reason: '$s should have hint');
        expect(s.label.isNotEmpty, isTrue, reason: '$s should have label');
      }
    });
  });
}
