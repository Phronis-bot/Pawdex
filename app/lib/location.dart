import 'dart:async';

import 'package:geolocator/geolocator.dart';

import 'telegram.dart';

class LocationUnavailable implements Exception {
  LocationUnavailable(this.message);
  final String message;
}

typedef Location = ({double latitude, double longitude});

/// Current location, asking for permission if needed.
///
/// Inside Telegram, Telegram's own location dialog is tried first; everywhere else (and
/// as a fallback) the device/browser location. Never waits forever: some web views never
/// show the browser's permission prompt, so the whole attempt is capped.
Future<Location> currentLocation() async {
  final viaTelegram = await telegramLocation();
  if (viaTelegram != null) return viaTelegram;
  try {
    return await _deviceLocation().timeout(const Duration(seconds: 20));
  } on TimeoutException {
    throw LocationUnavailable(
      "Couldn't get your location. Allow location access for Pawdex (in Telegram: ⋮ → "
      'Settings), or try on your phone.',
    );
  }
}

Future<Location> _deviceLocation() async {
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
  final position = await Geolocator.getCurrentPosition(
    locationSettings: const LocationSettings(
      accuracy: LocationAccuracy.high,
      timeLimit: Duration(seconds: 15),
    ),
  );
  return (latitude: position.latitude, longitude: position.longitude);
}
