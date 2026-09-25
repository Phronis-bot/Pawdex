import 'package:geolocator/geolocator.dart';

class LocationUnavailable implements Exception {
  LocationUnavailable(this.message);
  final String message;
}

/// Current position, asking for permission if needed.
Future<Position> currentPosition() async {
  if (!await Geolocator.isLocationServiceEnabled()) {
    throw LocationUnavailable('Turn on location to log where you met this animal.');
  }
  var permission = await Geolocator.checkPermission();
  if (permission == LocationPermission.denied) {
    permission = await Geolocator.requestPermission();
  }
  if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
    throw LocationUnavailable('Pawdex needs location access to log a sighting.');
  }
  return Geolocator.getCurrentPosition(
    locationSettings: const LocationSettings(
      accuracy: LocationAccuracy.high,
      timeLimit: Duration(seconds: 15),
    ),
  );
}
