import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

enum Species { cat, dog }

class Sighting {
  Sighting({
    required this.id,
    required this.species,
    required this.confidence,
    required this.createdAt,
  });

  factory Sighting.fromJson(Map<String, dynamic> json) => Sighting(
        id: json['id'] as String,
        species: Species.values.byName(json['species'] as String),
        confidence: (json['confidence'] as num).toDouble(),
        createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
      );

  final String id;
  final Species species;
  final double confidence;
  final DateTime createdAt;
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

  Future<Sighting> createSighting({
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
      return Sighting.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
    }
    final detail = _detail(response);
    if (response.statusCode == 422 && detail is Map && detail['code'] == 'no_animal') {
      throw NoAnimalException(detail['message'] as String);
    }
    throw ApiException(response.statusCode, detail.toString());
  }

  Future<List<Sighting>> mySightings() async {
    final response = await client.get(Uri.parse('$baseUrl/sightings/mine'), headers: _headers);
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode, _detail(response).toString());
    }
    return (jsonDecode(response.body) as List)
        .map((e) => Sighting.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<Uint8List> sightingPhoto(String sightingId) async {
    final response = await client.get(
      Uri.parse('$baseUrl/sightings/$sightingId/photo'),
      headers: _headers,
    );
    if (response.statusCode != 200) {
      throw ApiException(response.statusCode, 'Photo not available');
    }
    return response.bodyBytes;
  }

  static Object _detail(http.Response response) {
    try {
      return (jsonDecode(response.body) as Map<String, dynamic>)['detail'] ?? response.body;
    } on FormatException {
      return response.body;
    }
  }
}
