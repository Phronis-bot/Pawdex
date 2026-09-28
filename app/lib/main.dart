import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'api.dart';
import 'config.dart';
import 'device_id.dart';
import 'map_screen.dart';
import 'sightings_screen.dart';
import 'snap_screen.dart';
import 'telegram.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Inside Telegram the player is their Telegram account; elsewhere, this device.
  final initData = telegramInitData();
  final userId = initData == null ? await loadOrCreateUserId() : '';
  runApp(PawdexApp(
    api: ApiClient(
      baseUrl: apiBaseUrl,
      userId: userId,
      telegramInitData: initData,
      client: http.Client(),
    ),
  ));
}

class PawdexApp extends StatelessWidget {
  const PawdexApp({super.key, required this.api});

  final ApiClient api;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Pawdex',
      theme: ThemeData(colorSchemeSeed: Colors.orange, useMaterial3: true),
      home: HomeShell(api: api),
    );
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.api});

  final ApiClient api;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;
  late final Future<String> _nickname = widget.api.myNickname();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pawdex'),
        actions: [
          FutureBuilder<String>(
            future: _nickname,
            builder: (context, snapshot) => snapshot.hasData
                ? Padding(
                    padding: const EdgeInsets.only(right: 16),
                    child: Chip(avatar: const Icon(Icons.person, size: 18), label: Text(snapshot.data!)),
                  )
                : const SizedBox.shrink(),
          ),
        ],
      ),
      // No IndexedStack on purpose: tabs refetch their data every time they are opened.
      body: switch (_tab) {
        0 => SnapScreen(api: widget.api),
        1 => MapScreen(api: widget.api),
        _ => SightingsScreen(api: widget.api),
      },
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.photo_camera), label: 'Snap'),
          NavigationDestination(icon: Icon(Icons.map), label: 'Map'),
          NavigationDestination(icon: Icon(Icons.collections), label: 'My sightings'),
        ],
      ),
    );
  }
}
