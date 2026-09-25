import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'api.dart';
import 'config.dart';
import 'device_id.dart';
import 'sightings_screen.dart';
import 'snap_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final userId = await loadOrCreateUserId();
  runApp(PawdexApp(
    api: ApiClient(baseUrl: apiBaseUrl, userId: userId, client: http.Client()),
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Pawdex')),
      // No IndexedStack on purpose: "My sightings" refetches every time it is opened.
      body: switch (_tab) {
        0 => SnapScreen(api: widget.api),
        _ => SightingsScreen(api: widget.api),
      },
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.photo_camera), label: 'Snap'),
          NavigationDestination(icon: Icon(Icons.collections), label: 'My sightings'),
        ],
      ),
    );
  }
}
