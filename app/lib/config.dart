import 'package:flutter/foundation.dart';

/// Base URL of the Pawdex API.
///
/// Override with `--dart-define=API_BASE_URL=http://192.168.1.10:8000`
/// (e.g. when running on a physical phone). By default the Android emulator
/// reaches the host machine via 10.0.2.2, everything else via localhost.
String get apiBaseUrl {
  const override = String.fromEnvironment('API_BASE_URL');
  if (override.isNotEmpty) return override;
  if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
    return 'http://10.0.2.2:8000';
  }
  return 'http://localhost:8000';
}
