import 'package:flutter_test/flutter_test.dart';
import 'package:aitrading_app/app.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const PumpSignalApp());
    expect(find.text('今日信号'), findsOneWidget);
    expect(find.text('历史追踪'), findsOneWidget);
  });
}
