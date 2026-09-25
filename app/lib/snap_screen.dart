import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import 'api.dart';
import 'location.dart';
import 'species_label.dart';

class SnapScreen extends StatefulWidget {
  const SnapScreen({super.key, required this.api});

  final ApiClient api;

  @override
  State<SnapScreen> createState() => _SnapScreenState();
}

class _SnapScreenState extends State<SnapScreen> {
  final _picker = ImagePicker();
  bool _busy = false;
  Widget? _result;

  Future<void> _snap(ImageSource source) async {
    final file = await _picker.pickImage(source: source, maxWidth: 1600, imageQuality: 85);
    if (file == null) return;

    setState(() {
      _busy = true;
      _result = null;
    });
    try {
      final position = await currentPosition();
      final sighting = await widget.api.createSighting(
        photo: await file.readAsBytes(),
        latitude: position.latitude,
        longitude: position.longitude,
      );
      _show(Icons.pets, '${speciesLabel(sighting.species)}!',
          'Saved to your sightings (${(sighting.confidence * 100).round()}% sure).');
    } on NoAnimalException catch (e) {
      _show(Icons.search_off, 'No cat or dog', e.message);
    } on LocationUnavailable catch (e) {
      _show(Icons.location_off, 'No location', e.message);
    } catch (e) {
      _show(Icons.error_outline, 'Something went wrong', '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _show(IconData icon, String title, String message) {
    if (!mounted) return;
    setState(() {
      _result = Card(
        child: ListTile(
          leading: Icon(icon, size: 36),
          title: Text(title),
          subtitle: Text(message),
        ),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Met a street cat or dog?', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _busy ? null : () => _snap(ImageSource.camera),
              icon: const Icon(Icons.photo_camera),
              label: const Text('Take a photo'),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _busy ? null : () => _snap(ImageSource.gallery),
              icon: const Icon(Icons.photo_library),
              label: const Text('Choose from gallery'),
            ),
            const SizedBox(height: 24),
            if (_busy) const CircularProgressIndicator(),
            if (_result != null) _result!,
          ],
        ),
      ),
    );
  }
}
