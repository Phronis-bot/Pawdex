import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:latlong2/latlong.dart';

import 'package:pawdex/api.dart';
import 'package:pawdex/map_screen.dart';

import 'fixtures.dart';

void main() {
  testWidgets('shows zone badges and lists who lives in a tapped zone', (tester) async {
    final requested = <String>[];
    final api = ApiClient(
      baseUrl: 'http://api',
      userId: 'u',
      client: MockClient((request) async {
        requested.add(request.url.path);
        return switch (request.url.path) {
          '/map/zones' => jsonResponse([zoneJson(cell: 'c1', cats: 2, dogs: 1)]),
          '/map/zones/c1/animals' => jsonResponse([
              animalJson(id: 'm', name: 'Mo', count: 14),
              animalJson(id: 'r', species: 'dog', count: 1),
            ]),
          _ => http.Response('', 404),
        };
      }),
    );

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: MapScreen(api: api, locate: () async => const LatLng(10.77, 106.7))),
    ));
    await tester.pumpAndSettle();

    expect(requested, contains('/map/zones'));
    expect(find.text('🐱2 🐶1'), findsOneWidget);

    await tester.tap(find.text('🐱2 🐶1'));
    await tester.pumpAndSettle();

    expect(find.text('Who lives here'), findsOneWidget);
    expect(find.text('Mo'), findsOneWidget);
    expect(find.text('Cat · seen 14 times'), findsOneWidget);
    expect(find.text('Unnamed dog'), findsOneWidget);
  });
}
