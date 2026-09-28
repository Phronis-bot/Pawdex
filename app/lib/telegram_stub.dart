/// Not running inside Telegram (Android/iOS app).
String? telegramInitData() => null;

Future<({double latitude, double longitude})?> telegramLocation() async => null;
