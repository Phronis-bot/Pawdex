/// Telegram Mini App bridge. On the web build inside Telegram it returns the signed
/// player data (initData); everywhere else it returns null.
library;

export 'telegram_stub.dart' if (dart.library.js_interop) 'telegram_web.dart';
