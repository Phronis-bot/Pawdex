import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:pawdex/main.dart';

void main() {
  testWidgets('shows greeting and /health response', (tester) async {
    final client = MockClient((request) async {
      expect(request.url.path, '/health');
      return http.Response('{"status": "ok", "db": "ok"}', 200);
    });

    await tester.pumpWidget(PawdexApp(client: client));
    await tester.pumpAndSettle();

    expect(find.text('Hello Pawdex'), findsOneWidget);
    expect(find.textContaining('"status": "ok"'), findsOneWidget);
  });
}
