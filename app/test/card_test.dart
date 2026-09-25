import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:pawdex/animal_card_screen.dart';
import 'package:pawdex/api.dart';
import 'package:pawdex/share_card.dart';

import 'fixtures.dart';

const siamese = {
  'name': 'Siamese',
  'origin': 'Thailand',
  'history': 'One of the oldest known breeds.',
  'relatives': 'Cousin of the Birman.',
  'facts': ['Very talkative.', 'Points darken in the cold.'],
};

void main() {
  test('animal card parses discoverer, coat and chronicle', () {
    final card = AnimalCard.fromJson(cardJson());

    expect(card.animal.rarity, Rarity.legendary);
    expect(card.discoveredBy, 'Sleepy Mango');
    expect(card.coat, 'Calico');
    expect(card.chronicle.map((e) => e.sightingId), ['s1', 's2']);
    expect(card.chronicle.last.byMe, isTrue);
  });

  testWidgets('card screen shows rarity, coat fact and chronicle', (tester) async {
    final api = ApiClient(
      baseUrl: 'http://api',
      userId: 'u',
      client: MockClient((request) async =>
          request.url.path == '/animals/mo' ? jsonResponse(cardJson()) : http.Response('', 404)),
    );

    await tester.pumpWidget(MaterialApp(home: AnimalCardScreen(api: api, animalId: 'mo')));
    await tester.pumpAndSettle();

    // The page itself, not the chronicle grid nested inside it.
    final page = find.byType(Scrollable).first;
    await tester.scrollUntilVisible(find.text('★★★ Legendary'), 200, scrollable: page);
    expect(find.text('Cat · Mixed breed · Calico'), findsOneWidget);
    expect(find.text('Discovered by Sleepy Mango'), findsOneWidget);
    expect(find.textContaining('Seen 2 times'), findsOneWidget);

    await tester.scrollUntilVisible(find.text('In Japan calicos are considered lucky.'), 200, scrollable: page);
    expect(find.text('Did you know? · Calico coat'), findsOneWidget);
    expect(find.text('Calico cats are almost always female.'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('by you'), 200, scrollable: page);
    expect(find.text('by Sleepy Mango'), findsOneWidget);
  });

  testWidgets('card screen shows the breed block only when there is a breed', (tester) async {
    Future<void> open(Map<String, dynamic> json) async {
      final api = ApiClient(
        baseUrl: 'http://api',
        userId: 'u',
        client: MockClient((request) async =>
            request.url.path == '/animals/mo' ? jsonResponse(json) : http.Response('', 404)),
      );
      await tester.pumpWidget(MaterialApp(home: AnimalCardScreen(key: UniqueKey(), api: api, animalId: 'mo')));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Did you know? · Calico coat'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
    }

    await open(cardJson(breed: siamese));
    expect(find.text('Cat · Siamese · Calico'), findsOneWidget);
    expect(find.text('Siamese · from Thailand'), findsOneWidget);
    expect(find.text('One of the oldest known breeds.'), findsOneWidget);
    expect(find.text('Relatives & look-alikes'), findsOneWidget);
    expect(find.text('Cousin of the Birman.'), findsOneWidget);
    expect(find.text('Very talkative.'), findsOneWidget);

    await open(cardJson());
    expect(find.textContaining('from Thailand'), findsNothing);
    expect(find.text('Mixed breed'), findsOneWidget);
  });

  testWidgets('share card shows name, rarity and discoverer but no place', (tester) async {
    final card = AnimalCard.fromJson(cardJson());
    // 1x1 transparent PNG.
    final photo = Uint8List.fromList(const [
      137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82, 0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0, //
      31, 21, 196, 137, 0, 0, 0, 13, 73, 68, 65, 84, 120, 156, 99, 0, 1, 0, 0, 5, 0, 1, 13, 10, 45, 180, 0, //
      0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130,
    ]);

    await tester.pumpWidget(MaterialApp(home: Scaffold(body: ShareCard(card: card, photo: photo))));

    expect(find.text('Mo'), findsOneWidget);
    expect(find.text('LEGENDARY'), findsOneWidget);
    expect(find.text('Cat · Mixed breed · Calico'), findsOneWidget);
    expect(find.text('Seen 2 times · discovered by Sleepy Mango'), findsOneWidget);

    final withBreed = AnimalCard.fromJson(cardJson(breed: siamese));
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: ShareCard(card: withBreed, photo: photo))));
    expect(find.text('Cat · Siamese · Calico'), findsOneWidget);
    expect(find.text('from Thailand'), findsOneWidget);
  });
}
