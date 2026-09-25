import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

enum Species { cat, dog }

/// Server's verdict on a new photo.
enum Outcome {
  /// Confident: "It's Mo!"
  match,

  /// Ask the player: "Mo, or someone new?"
  uncertain,

  /// Nobody similar nearby.
  newAnimal,
}

class AnimalRef {
  AnimalRef({required this.id, required this.name, required this.canName});

  factory AnimalRef.fromJson(Map<String, dynamic> json) => AnimalRef(
        id: json['id'] as String,
        name: json['name'] as String?,
        canName: json['can_name'] as bool,
      );

  final String id;
  final String? name;
  final bool canName;
}

class Animal {
  Animal({
    required this.id,
    required this.species,
    required this.name,
    required this.sightingsCount,
    required this.canName,
  });

  factory Animal.fromJson(Map<String, dynamic> json) => Animal(
        id: json['id'] as String,
        species: Species.values.byName(json['species'] as String),
        name: json['name'] as String?,
        sightingsCount: json['sightings_count'] as int,
        canName: json['can_name'] as bool,
      );

  final String id;
  final Species species;
  final String? name;
  final int sightingsCount;

  /// True for the discoverer until the name is set.
  final bool canName;
}

class Sighting {
  Sighting({
    required this.id,
    required this.species,
    required this.confidence,
    required this.createdAt,
    required this.pending,
    required this.animal,
  });

  factory Sighting.fromJson(Map<String, dynamic> json) => Sighting(
        id: json['id'] as String,
        species: Species.values.byName(json['species'] as String),
        confidence: (json['confidence'] as num).toDouble(),
        createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
        pending: json['pending'] as bool,
        animal: json['animal'] == null
            ? null
            : AnimalRef.fromJson(json['animal'] as Map<String, dynamic>),
      );

  final String id;
  final Species species;
  final double confidence;
  final DateTime createdAt;

  /// Waiting for the player to say which animal this is.
  final bool pending;
  final AnimalRef? animal;
}

class Candidate {
  Candidate({required this.animal, required this.similarity});

  factory Candidate.fromJson(Map<String, dynamic> json) => Candidate(
        animal: Animal.fromJson(json['animal'] as Map<String, dynamic>),
        similarity: (json['similarity'] as num).toDouble(),
      );

  final Animal animal;
  final double similarity;
}

class SightingResult {
  SightingResult({
    required this.sighting,
    required this.outcome,
    required this.animal,
    required this.candidates,
  });

  factory SightingResult.fromJson(Map<String, dynamic> json) => SightingResult(
        sighting: Sighting.fromJson(json['sighting'] as Map<String, dynamic>),
        outcome: switch (json['outcome'] as String) {
          'match' => Outcome.match,
          'uncertain' => Outcome.uncertain,
          _ => Outcome.newAnimal,
        },
        animal: json['animal'] == null
            ? null
            : Animal.fromJson(json['animal'] as Map<String, dynamic>),
        candidates: (json['candidates'] as List)
            .map((c) => Candidate.fromJson(c as Map<String, dynamic>))
            .toList(),
      );

  final Sighting sighting;
  final Outcome outcome;

  /// Null while the outcome is uncertain.
  final Animal? animal;

  /// Only filled for [Outcome.uncertain].
  final List<Candidate> candidates;
}

/// The server looked at the photo and found no cat or dog.
class NoAnimalException implements Exception {
  NoAnimalException(this.message);
  final String message;
}

class ApiException implements Exception {
  ApiException(this.statusCode, this.message);
  final int statusCode;
  final String message;

  @override
  String toString() => 'HTTP $statusCode: $message';
}

class ApiClient {
  ApiClient({required this.baseUrl, required this.userId, required this.client});

  final String baseUrl;
  final String userId;
  final http.Client client;

  Map<String, String> get _headers => {'X-User-Id': userId};
  Map<String, String> get _jsonHeaders => {..._headers, 'Content-Type': 'application/json'};

  Future<SightingResult> createSighting({
    required Uint8List photo,
    required double latitude,
    required double longitude,
  }) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/sightings'))
      ..headers.addAll(_headers)
      ..fields['latitude'] = latitude.toString()
      ..fields['longitude'] = longitude.toString()
      ..files.add(http.MultipartFile.fromBytes('photo', photo, filename: 'photo.jpg'));
    final response = await http.Response.fromStream(await client.send(request));

    if (response.statusCode == 201) {
      return SightingResult.fromJson(_json(response) as Map<String, dynamic>);
    }
    final detail = _detail(response);
    if (response.statusCode == 422 && detail is Map && detail['code'] == 'no_animal') {
      throw NoAnimalException(detail['message'] as String);
    }
    throw ApiException(response.statusCode, detail.toString());
  }

  Future<List<Sighting>> mySightings() async {
    final response = await client.get(Uri.parse('$baseUrl/sightings/mine'), headers: _headers);
    _check(response);
    return (_json(response) as List)
        .map((e) => Sighting.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<Candidate>> candidates(String sightingId) async {
    final response = await client.get(
      Uri.parse('$baseUrl/sightings/$sightingId/candidates'),
      headers: _headers,
    );
    _check(response);
    return (_json(response) as List)
        .map((e) => Candidate.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Answer "Is it one of these?": a candidate's id, or null for a new animal.
  Future<SightingResult> resolve(String sightingId, {String? animalId}) async {
    final response = await client.post(
      Uri.parse('$baseUrl/sightings/$sightingId/resolve'),
      headers: _jsonHeaders,
      body: jsonEncode({'animal_id': animalId}),
    );
    _check(response);
    return SightingResult.fromJson(_json(response) as Map<String, dynamic>);
  }

  Future<Animal> nameAnimal(String animalId, String name) async {
    final response = await client.put(
      Uri.parse('$baseUrl/animals/$animalId/name'),
      headers: _jsonHeaders,
      body: jsonEncode({'name': name}),
    );
    _check(response);
    return Animal.fromJson(_json(response) as Map<String, dynamic>);
  }

  Future<Uint8List> sightingPhoto(String sightingId) =>
      _photo('$baseUrl/sightings/$sightingId/photo');

  Future<Uint8List> animalPhoto(String animalId) => _photo('$baseUrl/animals/$animalId/photo');

  Future<Uint8List> _photo(String url) async {
    final response = await client.get(Uri.parse(url), headers: _headers);
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode, 'Photo not available');
    }
    return response.bodyBytes;
  }

  static Object? _json(http.Response response) => jsonDecode(utf8.decode(response.bodyBytes));

  static void _check(http.Response response) {
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode, _detail(response).toString());
    }
  }

  static Object _detail(http.Response response) {
    try {
      return (_json(response) as Map<String, dynamic>)['detail'] ?? response.body;
    } on FormatException {
      return response.body;
    }
  }
}
