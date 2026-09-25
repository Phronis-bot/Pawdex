import 'package:flutter/material.dart';

import 'api.dart';
import 'photo_view.dart';
import 'species_label.dart';

/// "Is it one of these, or someone new?" Pops with the server's [SightingResult].
class ConfirmScreen extends StatefulWidget {
  const ConfirmScreen({
    super.key,
    required this.api,
    required this.sighting,
    required this.candidates,
  });

  final ApiClient api;
  final Sighting sighting;
  final List<Candidate> candidates;

  @override
  State<ConfirmScreen> createState() => _ConfirmScreenState();
}

class _ConfirmScreenState extends State<ConfirmScreen> {
  bool _busy = false;

  Future<void> _answer(String? animalId) async {
    setState(() => _busy = true);
    try {
      final result = await widget.api.resolve(widget.sighting.id, animalId: animalId);
      if (mounted) Navigator.pop(context, result);
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not save: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final word = speciesWord(widget.sighting.species);
    return Scaffold(
      appBar: AppBar(title: const Text('Have you met before?')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Center(
            child: ApiPhoto(load: () => widget.api.sightingPhoto(widget.sighting.id), size: 200),
          ),
          const SizedBox(height: 16),
          Text(
            'This $word looks like someone who lives nearby. Is it one of them?',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 16),
          for (final c in widget.candidates)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Row(
                  children: [
                    ApiPhoto(load: () => widget.api.animalPhoto(c.animal.id), size: 72),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(animalTitle(c.animal.name, c.animal.species),
                              style: Theme.of(context).textTheme.titleMedium),
                          Text('Seen ${c.animal.sightingsCount} '
                              '${c.animal.sightingsCount == 1 ? 'time' : 'times'}'),
                        ],
                      ),
                    ),
                    FilledButton(
                      onPressed: _busy ? null : () => _answer(c.animal.id),
                      child: const Text("That's them"),
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 16),
          OutlinedButton(
            onPressed: _busy ? null : () => _answer(null),
            child: Text('No, a new $word'),
          ),
        ],
      ),
    );
  }
}
