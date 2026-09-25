import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

const _key = 'device_user_id';

/// Anonymous player id: generated once and kept on the device.
Future<String> loadOrCreateUserId() async {
  final prefs = await SharedPreferences.getInstance();
  final existing = prefs.getString(_key);
  if (existing != null) return existing;
  final id = const Uuid().v4();
  await prefs.setString(_key, id);
  return id;
}
