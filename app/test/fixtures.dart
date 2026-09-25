import 'dart:convert';

import 'package:http/http.dart' as http;

http.Response jsonResponse(Object body, [int status = 200]) => http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      status,
      headers: {'content-type': 'application/json'},
    );

Map<String, dynamic> animalJson({
  String id = 'a1',
  String species = 'cat',
  String? name,
  int count = 1,
  bool canName = false,
  String? rarity = 'common',
}) =>
    {
      'id': id,
      'species': species,
      'name': name,
      'sightings_count': count,
      'can_name': canName,
      'rarity': rarity,
    };

Map<String, dynamic> cardJson({
  String? name = 'Mo',
  String rarity = 'legendary',
  Map<String, dynamic>? breed,
}) =>
    {
      ...animalJson(id: 'mo', name: name, count: 2, rarity: rarity),
      'discovered_by': 'Sleepy Mango',
      'discovered_by_me': false,
      'coat': 'Calico',
      'coat_facts': [
        'Calico cats are almost always female.',
        'The patches are random.',
        'In Japan calicos are considered lucky.',
      ],
      'breed': breed,
      'chronicle': [
        {'sighting_id': 's1', 'created_at': '2026-09-20T10:00:00Z', 'by': 'Sleepy Mango', 'by_me': false},
        {'sighting_id': 's2', 'created_at': '2026-09-25T10:00:00Z', 'by': 'Brave Noodle', 'by_me': true},
      ],
    };

Map<String, dynamic> sightingJson({
  String id = 's1',
  String species = 'cat',
  bool pending = false,
  Map<String, dynamic>? animal,
}) =>
    {
      'id': id,
      'species': species,
      'confidence': 0.9,
      'created_at': '2026-09-25T10:00:00Z',
      'pending': pending,
      'animal': animal,
    };

Map<String, dynamic> zoneJson({String cell = '89xyz', int cats = 1, int dogs = 0}) => {
      'cell': cell,
      'center': [10.77, 106.7],
      'boundary': [
        for (var i = 0; i < 6; i++) [10.77 + 0.001 * i, 106.7]
      ],
      'cats': cats,
      'dogs': dogs,
    };

Map<String, dynamic> sightingResultJson({
  required String outcome,
  bool pending = false,
  Map<String, dynamic>? animal,
  List<Map<String, dynamic>> candidates = const [],
}) =>
    {
      'sighting': sightingJson(
        pending: pending,
        animal: animal == null
            ? null
            : {'id': animal['id'], 'name': animal['name'], 'can_name': animal['can_name']},
      ),
      'outcome': outcome,
      'animal': animal,
      'candidates': candidates,
    };
