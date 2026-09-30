import 'dart:async';
import 'dart:js_interop';

@JS('Telegram.WebApp')
external _WebApp? get _webApp;

extension type _WebApp._(JSObject _) implements JSObject {
  external String get initData;
  external void ready();
  external void expand();
  external bool isVersionAtLeast(String version);
  external void disableVerticalSwipes();
  @JS('LocationManager')
  external _LocationManager? get locationManager;
}

/// Telegram's own location API for Mini Apps (Bot API 8.0+): asks with Telegram's
/// permission dialog, which works where the browser prompt never shows up.
extension type _LocationManager._(JSObject _) implements JSObject {
  external bool get isInited;
  external bool get isLocationAvailable;
  external void init(JSFunction callback);
  external void getLocation(JSFunction callback);
}

extension type _LocationData._(JSObject _) implements JSObject {
  external double get latitude;
  external double get longitude;
}

/// Signed player data when opened from the Telegram bot, null in a normal browser.
String? telegramInitData() {
  final webApp = _webApp;
  final data = webApp?.initData ?? '';
  if (webApp == null || data.isEmpty) return null;
  webApp
    ..ready()
    ..expand(); // use the full screen height inside Telegram
  // Otherwise a swipe on a list drags the whole Mini App down instead of scrolling
  // (Bot API 7.7+; older Telegram has no such method).
  if (webApp.isVersionAtLeast('7.7')) webApp.disableVerticalSwipes();
  return data;
}

/// The player's location via Telegram, or null if Telegram can't provide it here
/// (older Telegram, desktop without location, or the player said no).
Future<({double latitude, double longitude})?> telegramLocation() async {
  final manager = _webApp?.locationManager;
  if (manager == null || (_webApp?.initData ?? '').isEmpty) return null;
  if (!manager.isInited) {
    final inited = Completer<void>();
    manager.init((() => inited.complete()).toJS);
    await inited.future.timeout(const Duration(seconds: 5), onTimeout: () {});
  }
  if (!manager.isInited || !manager.isLocationAvailable) return null;

  final result = Completer<_LocationData?>();
  manager.getLocation(((_LocationData? data) => result.complete(data)).toJS);
  final data = await result.future.timeout(const Duration(seconds: 30), onTimeout: () => null);
  return data == null ? null : (latitude: data.latitude, longitude: data.longitude);
}
