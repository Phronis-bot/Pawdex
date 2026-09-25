import 'package:flutter/material.dart';

import 'api.dart';
import 'flows.dart';
import 'photo_view.dart';
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

  Future<void> _open(Sighting s) async {
    try {
      if (s.pending) {
        final candidates = await widget.api.candidates(s.id);
        if (!mounted) return;
        await completeSighting(
          context,
          widget.api,
          SightingResult(sighting: s, outcome: Outcome.uncertain, animal: null, candidates: candidates),
        );
      } else if (s.animal case final animal? when animal.canName) {
        await askName(context, widget.api, animalId: animal.id, species: s.species);
      } else {
        return;
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    }
    await _reload();
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
            itemBuilder: (context, i) {
              final s = sightings[i];
              return ListTile(
                key: ValueKey(s.id),
                leading: ApiPhoto(load: () => widget.api.sightingPhoto(s.id), size: 56),
                title: Text(_title(s)),
                subtitle: Text(_subtitle(s)),
                trailing: s.pending || (s.animal?.canName ?? false)
                    ? const Icon(Icons.chevron_right)
                    : null,
                onTap: () => _open(s),
              );
            },
          ),
        );
      },
    );
  }

  static String _title(Sighting s) {
    if (s.pending) return 'Who is this? Tap to tell us';
    final animal = s.animal;
    // Sightings from before animals existed have no animal.
    if (animal == null) return speciesLabel(s.species);
    return animalTitle(animal.name, s.species);
  }

  static String _subtitle(Sighting s) {
    final date = _formatDate(s.createdAt);
    return (s.animal?.canName ?? false) ? '$date · tap to name' : date;
  }

  static String _formatDate(DateTime d) {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${d.year}-${two(d.month)}-${two(d.day)} ${two(d.hour)}:${two(d.minute)}';
  }
}
