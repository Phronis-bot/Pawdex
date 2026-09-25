import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:pawdex/api.dart';
import 'package:pawdex/main.dart';

void main() {
  testWidgets('snap tab by default, my sightings tab lists sightings', (tester) async {
    final client = MockClient((request) async {
      if (request.url.path == '/sightings/mine') {
        return http.Response(
          jsonEncode([
            {'id': 'a', 'species': 'cat', 'confidence': 0.9, 'created_at': '2026-09-25T10:00:00Z'},
            {'id': 'b', 'species': 'dog', 'confidence': 0.8, 'created_at': '2026-09-24T10:00:00Z'},
          ]),
          200,
        );
      }
      return http.Response('', 404); // photos
    });
    final api = ApiClient(baseUrl: 'http://api', userId: 'u', client: client);

    await tester.pumpWidget(PawdexApp(api: api));
    expect(find.text('Take a photo'), findsOneWidget);
    expect(find.text('Choose from gallery'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.collections));
    await tester.pumpAndSettle();

    expect(find.text('Cat'), findsOneWidget);
    expect(find.text('Dog'), findsOneWidget);
  });
}
