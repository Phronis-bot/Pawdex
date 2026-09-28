import 'dart:js_interop';

@JS('Telegram.WebApp')
external _WebApp? get _webApp;

extension type _WebApp._(JSObject _) implements JSObject {
  external String get initData;
  external void ready();
  external void expand();
}

/// Signed player data when opened from the Telegram bot, null in a normal browser.
String? telegramInitData() {
  final webApp = _webApp;
  final data = webApp?.initData ?? '';
  if (webApp == null || data.isEmpty) return null;
  webApp
    ..ready()
    ..expand(); // use the full screen height inside Telegram
  return data;
}
