import 'package:flutter/material.dart';

import 'api.dart';
import 'photo_view.dart';
import 'species_label.dart';

/// The discoverer names a new animal. Pops with the named [Animal], or null for "later".
class NameScreen extends StatefulWidget {
  const NameScreen({super.key, required this.api, required this.animalId, required this.species});

  final ApiClient api;
  final String animalId;
  final Species species;

  @override
  State<NameScreen> createState() => _NameScreenState();
}

class _NameScreenState extends State<NameScreen> {
  final _name = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final name = _name.text.trim();
    if (name.isEmpty) return;
    setState(() => _busy = true);
    try {
      final animal = await widget.api.nameAnimal(widget.animalId, name);
      if (mounted) Navigator.pop(context, animal);
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not save the name: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final word = speciesWord(widget.species);
    return Scaffold(
      appBar: AppBar(title: Text('New $word discovered!')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Center(child: ApiPhoto(load: () => widget.api.animalPhoto(widget.animalId), size: 200)),
          const SizedBox(height: 24),
          Text(
            "You're the first to find this $word, so you get to name it.",
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _name,
            autofocus: true,
            maxLength: 30,
            textCapitalization: TextCapitalization.words,
            decoration: const InputDecoration(
              labelText: 'Name',
              helperText: 'Names are forever. Choose well!',
              border: OutlineInputBorder(),
            ),
            onChanged: (_) => setState(() {}),
            onSubmitted: (_) => _save(),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy || _name.text.trim().isEmpty ? null : _save,
            child: const Text('Save name'),
          ),
          TextButton(
            onPressed: _busy ? null : () => Navigator.pop(context),
            child: const Text('Later'),
          ),
        ],
      ),
    );
  }
}
