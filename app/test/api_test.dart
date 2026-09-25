import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:pawdex/api.dart';

import 'fixtures.dart';

ApiClient apiWith(MockClientHandler handler) =>
    ApiClient(baseUrl: 'http://api', userId: 'user-1', client: MockClient(handler));

void main() {
  test('createSighting sends photo, coordinates and user id', () async {
    late http.Request sent;
    final api = apiWith((request) async {
      sent = request;
      return jsonResponse(sightingResultJson(outcome: 'new', animal: animalJson(canName: true)), 201);
    });

    final result = await api.createSighting(
      photo: Uint8List.fromList([1, 2, 3]),
      latitude: 10.77,
      longitude: 106.70,
    );

    expect(sent.method, 'POST');
    expect(sent.url.toString(), 'http://api/sightings');
    expect(sent.headers['X-User-Id'], 'user-1');
    final body = utf8.decode(sent.bodyBytes, allowMalformed: true);
    expect(body, contains('name="latitude"'));
    expect(body, contains('10.77'));
    expect(body, contains('name="photo"'));
    expect(result.outcome, Outcome.newAnimal);
    expect(result.animal!.canName, isTrue);
  });

  test('createSighting parses an uncertain result with candidates', () async {
    final api = apiWith((_) async => jsonResponse(
          sightingResultJson(
            outcome: 'uncertain',
            pending: true,
            candidates: [
              {'animal': animalJson(name: 'Mo', count: 14), 'similarity': 0.61}
            ],
          ),
          201,
        ));

    final result = await api.createSighting(photo: Uint8List(0), latitude: 0, longitude: 0);

    expect(result.outcome, Outcome.uncertain);
    expect(result.animal, isNull);
    expect(result.sighting.pending, isTrue);
    expect(result.candidates.single.animal.name, 'Mo');
    expect(result.candidates.single.animal.sightingsCount, 14);
  });

  test('createSighting turns no_animal into NoAnimalException', () async {
    final api = apiWith((_) async => jsonResponse({
          'detail': {'code': 'no_animal', 'message': 'No cat or dog found in this photo.'}
        }, 422));

    expect(
      api.createSighting(photo: Uint8List(0), latitude: 0, longitude: 0),
      throwsA(isA<NoAnimalException>()),
    );
  });

  test('resolve sends the chosen animal, or null for a new one', () async {
    final bodies = <Object?>[];
    final api = apiWith((request) async {
      expect(request.url.path, '/sightings/s1/resolve');
      bodies.add(jsonDecode(request.body));
      return jsonResponse(sightingResultJson(outcome: 'match', animal: animalJson()));
    });

    await api.resolve('s1', animalId: 'a1');
    await api.resolve('s1');

    expect(bodies, [
      {'animal_id': 'a1'},
      {'animal_id': null},
    ]);
  });

  test('nameAnimal keeps non-ASCII names intact', () async {
    final api = apiWith((request) async {
      expect(request.method, 'PUT');
      expect(request.url.path, '/animals/a1/name');
      final name = (jsonDecode(request.body) as Map)['name'];
      return jsonResponse(animalJson(name: name as String));
    });

    final animal = await api.nameAnimal('a1', 'Mèo Béo');

    expect(animal.name, 'Mèo Béo');
  });

  test('mySightings parses pending and linked sightings', () async {
    final api = apiWith((request) async {
      expect(request.url.path, '/sightings/mine');
      return jsonResponse([
        sightingJson(id: 'a', pending: true),
        sightingJson(id: 'b', animal: {'id': 'x', 'name': 'Mo', 'can_name': false}),
      ]);
    });

    final list = await api.mySightings();

    expect(list[0].pending, isTrue);
    expect(list[1].animal!.name, 'Mo');
  });
}
