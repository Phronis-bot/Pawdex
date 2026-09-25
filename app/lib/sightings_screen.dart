import 'dart:typed_data';

import 'package:flutter/material.dart';

import 'api.dart';
import 'species_label.dart';

class SightingsScreen extends StatefulWidget {
  const SightingsScreen({super.key, required this.api});

  final ApiClient api;

  @override
  State<SightingsScreen> createState() => _SightingsScreenState();
}

class _SightingsScreenState extends State<SightingsScreen> {
  late Future<List<Sighting>> _sightings = widget.api.mySightings();

  Future<void> _reload() async {
    final next = widget.api.mySightings();
    setState(() => _sightings = next);
    await next;
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Sighting>>(
      future: _sightings,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('Could not load sightings\n${snapshot.error}', textAlign: TextAlign.center),
                TextButton(onPressed: _reload, child: const Text('Retry')),
              ],
            ),
          );
        }
        final sightings = snapshot.data!;
        if (sightings.isEmpty) {
          return const Center(child: Text('No sightings yet. Go find a cat!'));
        }
        return RefreshIndicator(
          onRefresh: _reload,
          child: ListView.builder(
            itemCount: sightings.length,
            itemBuilder: (context, i) => _SightingTile(api: widget.api, sighting: sightings[i]),
          ),
        );
      },
    );
  }
}

class _SightingTile extends StatefulWidget {
  const _SightingTile({required this.api, required this.sighting});

  final ApiClient api;
  final Sighting sighting;

  @override
  State<_SightingTile> createState() => _SightingTileState();
}

class _SightingTileState extends State<_SightingTile> {
  // Photos need the X-User-Id header, so they are fetched as bytes rather than Image.network.
  late final Future<Uint8List> _photo = widget.api.sightingPhoto(widget.sighting.id);

  @override
  Widget build(BuildContext context) {
    final s = widget.sighting;
    return ListTile(
      leading: SizedBox.square(
        dimension: 56,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: FutureBuilder<Uint8List>(
            future: _photo,
            builder: (context, snapshot) => snapshot.hasData
                ? Image.memory(snapshot.data!, fit: BoxFit.cover)
                : const ColoredBox(color: Colors.black12),
          ),
        ),
      ),
      title: Text(speciesLabel(s.species)),
      subtitle: Text(_formatDate(s.createdAt)),
    );
  }

  static String _formatDate(DateTime d) {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${d.year}-${two(d.month)}-${two(d.day)} ${two(d.hour)}:${two(d.minute)}';
  }
}
