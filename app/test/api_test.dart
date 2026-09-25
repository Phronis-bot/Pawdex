import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:pawdex/api.dart';

ApiClient apiWith(MockClientHandler handler) =>
    ApiClient(baseUrl: 'http://api', userId: 'user-1', client: MockClient(handler));

void main() {
  test('createSighting sends photo, coordinates and user id', () async {
    late http.Request sent;
    final api = apiWith((request) async {
      sent = request;
      return http.Response(
        jsonEncode({
          'id': 's1',
          'species': 'cat',
          'confidence': 0.93,
          'created_at': '2026-09-25T10:00:00Z',
        }),
        201,
      );
    });

    final sighting = await api.createSighting(
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
    expect(sighting.species, Species.cat);
  });

  test('createSighting turns no_animal into NoAnimalException', () async {
    final api = apiWith((_) async => http.Response(
          jsonEncode({
            'detail': {'code': 'no_animal', 'message': 'No cat or dog found in this photo.'}
          }),
          422,
        ));

    expect(
      api.createSighting(photo: Uint8List(0), latitude: 0, longitude: 0),
      throwsA(isA<NoAnimalException>()),
    );
  });

  test('mySightings parses the list', () async {
    final api = apiWith((request) async {
      expect(request.url.path, '/sightings/mine');
      return http.Response(
        jsonEncode([
          {'id': 'a', 'species': 'dog', 'confidence': 0.8, 'created_at': '2026-09-25T10:00:00Z'},
        ]),
        200,
      );
    });

    final list = await api.mySightings();

    expect(list.single.species, Species.dog);
  });
}
