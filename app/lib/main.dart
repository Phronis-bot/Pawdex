import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'config.dart';

void main() {
  runApp(PawdexApp(client: http.Client()));
}

class PawdexApp extends StatelessWidget {
  const PawdexApp({super.key, required this.client});

  final http.Client client;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Pawdex',
      theme: ThemeData(colorSchemeSeed: Colors.orange, useMaterial3: true),
      home: HelloScreen(client: client),
    );
  }
}

class HelloScreen extends StatefulWidget {
  const HelloScreen({super.key, required this.client});

  final http.Client client;

  @override
  State<HelloScreen> createState() => _HelloScreenState();
}

class _HelloScreenState extends State<HelloScreen> {
  late Future<String> _health;

  @override
  void initState() {
    super.initState();
    _health = _fetchHealth();
  }

  Future<String> _fetchHealth() async {
    final response = await widget.client
        .get(Uri.parse('$apiBaseUrl/health'))
        .timeout(const Duration(seconds: 5));
    final pretty = const JsonEncoder.withIndent('  ')
        .convert(jsonDecode(response.body));
    return 'HTTP ${response.statusCode}\n$pretty';
  }

  void _retry() {
    setState(() => _health = _fetchHealth());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Hello Pawdex',
                  style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 24),
              FutureBuilder<String>(
                future: _health,
                builder: (context, snapshot) {
                  if (snapshot.connectionState != ConnectionState.done) {
                    return const CircularProgressIndicator();
                  }
                  if (snapshot.hasError) {
                    return Text('API unreachable at $apiBaseUrl\n${snapshot.error}',
                        textAlign: TextAlign.center);
                  }
                  return Text(snapshot.data!,
                      style: const TextStyle(fontFamily: 'monospace'));
                },
              ),
              const SizedBox(height: 24),
              OutlinedButton(onPressed: _retry, child: const Text('Retry')),
            ],
          ),
        ),
      ),
    );
  }
}
