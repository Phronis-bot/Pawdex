import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:pawdex/api.dart';
import 'package:pawdex/confirm_screen.dart';
import 'package:pawdex/main.dart';
import 'package:pawdex/name_screen.dart';

import 'fixtures.dart';

ApiClient apiWith(MockClientHandler handler) =>
    ApiClient(baseUrl: 'http://api', userId: 'u', client: MockClient(handler));

/// Photos are irrelevant here; every other path goes to [handler].
MockClientHandler withoutPhotos(MockClientHandler handler) => (request) async =>
    request.url.path.endsWith('/photo') ? http.Response('', 404) : handler(request);

void main() {
  testWidgets('snap tab by default, my sightings tab lists sightings', (tester) async {
    final api = apiWith(withoutPhotos((request) async => jsonResponse([
          sightingJson(id: 'a', pending: true),
          sightingJson(id: 'b', animal: {'id': 'x', 'name': 'Mo', 'can_name': false}),
          sightingJson(id: 'c', species: 'dog', animal: {'id': 'y', 'name': null, 'can_name': true}),
        ])));

    await tester.pumpWidget(PawdexApp(api: api));
    expect(find.text('Take a photo'), findsOneWidget);
    expect(find.text('Choose from gallery'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.collections));
    await tester.pumpAndSettle();

    expect(find.text('Who is this? Tap to tell us'), findsOneWidget);
    expect(find.text('Mo'), findsOneWidget);
    expect(find.text('Unnamed dog'), findsOneWidget);
    expect(find.textContaining('tap to name'), findsOneWidget);
  });

  testWidgets('confirm screen resolves to the chosen candidate', (tester) async {
    Object? sentBody;
    final api = apiWith(withoutPhotos((request) async {
      sentBody = jsonDecode(request.body);
      return jsonResponse(sightingResultJson(outcome: 'match', animal: animalJson(id: 'mo', name: 'Mo')));
    }));
    SightingResult? popped;

    await tester.pumpWidget(MaterialApp(
      home: Builder(
        builder: (context) => TextButton(
          onPressed: () async {
            popped = await Navigator.push<SightingResult>(
              context,
              MaterialPageRoute(
                builder: (_) => ConfirmScreen(
                  api: api,
                  sighting: Sighting.fromJson(sightingJson(pending: true)),
                  candidates: [
                    Candidate(
                      animal: Animal.fromJson(animalJson(id: 'mo', name: 'Mo', count: 14)),
                      similarity: 0.6,
                    ),
                  ],
                ),
              ),
            );
          },
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    expect(find.text('Mo'), findsOneWidget);
    expect(find.text('Seen 14 times'), findsOneWidget);
    expect(find.text('No, a new cat'), findsOneWidget);

    await tester.tap(find.text("That's them"));
    await tester.pumpAndSettle();

    expect(sentBody, {'animal_id': 'mo'});
    expect(popped!.animal!.name, 'Mo');
  });

  testWidgets('name screen saves the trimmed name', (tester) async {
    Object? sentBody;
    final api = apiWith(withoutPhotos((request) async {
      sentBody = jsonDecode(request.body);
      return jsonResponse(animalJson(name: 'Fat Mo'));
    }));

    await tester.pumpWidget(MaterialApp(
      home: NameScreen(api: api, animalId: 'a1', species: Species.cat),
    ));
    await tester.pumpAndSettle();

    expect(find.text('New cat discovered!'), findsOneWidget);
    await tester.enterText(find.byType(TextField), '  Fat Mo ');
    await tester.pump();
    await tester.ensureVisible(find.text('Save name'));
    await tester.tap(find.text('Save name'));
    await tester.pumpAndSettle();

    expect(sentBody, {'name': 'Fat Mo'});
  });
}
