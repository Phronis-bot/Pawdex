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

enum Rarity { common, rare, legendary }

Rarity? _rarity(Object? value) => value == null ? null : Rarity.values.byName(value as String);

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
    required this.rarity,
  });

  factory Animal.fromJson(Map<String, dynamic> json) => Animal(
        id: json['id'] as String,
        species: Species.values.byName(json['species'] as String),
        name: json['name'] as String?,
        sightingsCount: json['sightings_count'] as int,
        canName: json['can_name'] as bool,
        rarity: _rarity(json['rarity']),
      );

  final String id;
  final Species species;
  final String? name;
  final int sightingsCount;

  /// True for the discoverer until the name is set.
  final bool canName;

  /// Null only for old animals that were never given a coat.
  final Rarity? rarity;
}

class ChronicleEntry {
  ChronicleEntry({required this.sightingId, required this.createdAt, required this.by, required this.byMe});

  factory ChronicleEntry.fromJson(Map<String, dynamic> json) => ChronicleEntry(
        sightingId: json['sighting_id'] as String,
        createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
        by: json['by'] as String,
        byMe: json['by_me'] as bool,
      );

  final String sightingId;
  final DateTime createdAt;

  /// Photographer's nickname.
  final String by;
  final bool byMe;
}

class BreedInfo {
  BreedInfo({required this.name, required this.origin, required this.history});

  factory BreedInfo.fromJson(Map<String, dynamic> json) => BreedInfo(
        name: json['name'] as String,
        origin: json['origin'] as String,
        history: json['history'] as String,
      );

  final String name;
  final String origin;
  final String history;
}

/// Everything on an animal's card. Carries no location.
class AnimalCard {
  AnimalCard({
    required this.animal,
    required this.discoveredBy,
    required this.discoveredByMe,
    required this.coat,
    required this.coatFacts,
    required this.breed,
    required this.chronicle,
  });

  factory AnimalCard.fromJson(Map<String, dynamic> json) => AnimalCard(
        animal: Animal.fromJson(json),
        discoveredBy: json['discovered_by'] as String,
        discoveredByMe: json['discovered_by_me'] as bool,
        coat: json['coat'] as String?,
        coatFacts: (json['coat_facts'] as List).cast<String>(),
        breed: json['breed'] == null ? null : BreedInfo.fromJson(json['breed'] as Map<String, dynamic>),
        chronicle: (json['chronicle'] as List)
            .map((e) => ChronicleEntry.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  final Animal animal;
  final String discoveredBy;
  final bool discoveredByMe;
  final String? coat;
  final List<String> coatFacts;

  /// Only when the server was confident; null for mixed breed.
  final BreedInfo? breed;

  /// Oldest first.
  final List<ChronicleEntry> chronicle;
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

/// A map zone (H3 hexagon, ~350 m across). The server never sends exact animal locations.
class Zone {
  Zone({
    required this.cell,
    required this.center,
    required this.boundary,
    required this.cats,
    required this.dogs,
  });

  factory Zone.fromJson(Map<String, dynamic> json) {
    (double, double) point(Object? p) {
      final list = p as List;
      return ((list[0] as num).toDouble(), (list[1] as num).toDouble());
    }

    return Zone(
      cell: json['cell'] as String,
      center: point(json['center']),
      boundary: (json['boundary'] as List).map(point).toList(),
      cats: json['cats'] as int,
      dogs: json['dogs'] as int,
    );
  }

  final String cell;

  /// (lat, lon) of the hexagon's centre and corners.
  final (double, double) center;
  final List<(double, double)> boundary;
  final int cats;
  final int dogs;
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

  Future<AnimalCard> animalCard(String animalId) async {
    final response = await client.get(Uri.parse('$baseUrl/animals/$animalId'), headers: _headers);
    _check(response);
    return AnimalCard.fromJson(_json(response) as Map<String, dynamic>);
  }

  /// The player's generated nickname.
  Future<String> myNickname() async {
    final response = await client.get(Uri.parse('$baseUrl/me'), headers: _headers);
    _check(response);
    return (_json(response) as Map<String, dynamic>)['nickname'] as String;
  }

  Future<List<Zone>> zones({
    required double latitude,
    required double longitude,
    required double radiusMeters,
  }) async {
    final uri = Uri.parse('$baseUrl/map/zones').replace(queryParameters: {
      'lat': latitude.toString(),
      'lon': longitude.toString(),
      'radius_m': radiusMeters.round().toString(),
    });
    final response = await client.get(uri, headers: _headers);
    _check(response);
    return (_json(response) as List).map((e) => Zone.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<Animal>> zoneAnimals(String cell) async {
    final response = await client.get(Uri.parse('$baseUrl/map/zones/$cell/animals'), headers: _headers);
    _check(response);
    return (_json(response) as List).map((e) => Animal.fromJson(e as Map<String, dynamic>)).toList();
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
