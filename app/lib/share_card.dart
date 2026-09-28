import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:share_plus/share_plus.dart';

import 'api.dart';
import 'rarity.dart';
import 'species_label.dart';

/// Preview of the social-media card with a Share button. The card deliberately shows
/// no place names or map: a shared picture must not help anyone find the animal.
/// (The breed's country of origin is history, not the animal's location.)
class ShareCardScreen extends StatefulWidget {
  const ShareCardScreen({super.key, required this.api, required this.card});

  final ApiClient api;
  final AnimalCard card;

  @override
  State<ShareCardScreen> createState() => _ShareCardScreenState();
}

class _ShareCardScreenState extends State<ShareCardScreen> {
  final _boundary = GlobalKey();
  late final Future<Uint8List> _photo = widget.api.animalPhoto(widget.card.animal.id);
  bool _busy = false;

  Future<void> _share() async {
    setState(() => _busy = true);
    try {
      final render = _boundary.currentContext!.findRenderObject()! as RenderRepaintBoundary;
      final image = await render.toImage(pixelRatio: 3);
      final png = (await image.toByteData(format: ui.ImageByteFormat.png))!.buffer.asUint8List();
      final animal = widget.card.animal;
      final title = animalTitle(animal.name, animal.species);
      await SharePlus.instance.share(ShareParams(
        files: [XFile.fromData(png, mimeType: 'image/png')],
        fileNameOverrides: ['pawdex-${title.toLowerCase().replaceAll(RegExp(r'\W+'), '-')}.png'],
        text: 'Meet $title on Pawdex!',
      ));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not share: $e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Share')),
      body: FutureBuilder<Uint8List>(
        future: _photo,
        builder: (context, snapshot) {
          if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
          if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
          return ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Center(
                child: RepaintBoundary(
                  key: _boundary,
                  child: ShareCard(card: widget.card, photo: snapshot.data!),
                ),
              ),
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: _busy ? null : _share,
                icon: const Icon(Icons.share),
                label: const Text('Share'),
              ),
            ],
          );
        },
      ),
    );
  }
}

class ShareCard extends StatelessWidget {
  const ShareCard({super.key, required this.card, required this.photo});

  final AnimalCard card;
  final Uint8List photo;

  @override
  Widget build(BuildContext context) {
    final animal = card.animal;
    final rarity = animal.rarity ?? Rarity.common;
    final seen = animal.sightingsCount;
    const white = TextStyle(color: Colors.white);
    return Container(
      width: 320,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [rarity.color, Color.lerp(rarity.color, Colors.black, 0.45)!],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('★' * rarity.stars, style: white.copyWith(fontSize: 18)),
              const SizedBox(width: 6),
              Expanded(
                child: Text(rarity.label.toUpperCase(),
                    overflow: TextOverflow.fade,
                    softWrap: false,
                    style: white.copyWith(fontWeight: FontWeight.w800, letterSpacing: 1.2)),
              ),
              Text('PAWDEX', style: white.copyWith(fontWeight: FontWeight.w900, letterSpacing: 1.5)),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: AspectRatio(aspectRatio: 1, child: Image.memory(photo, fit: BoxFit.cover)),
          ),
          const SizedBox(height: 12),
          Text(animalTitle(animal.name, animal.species),
              style: white.copyWith(fontSize: 30, fontWeight: FontWeight.w800)),
          Text(
            [
              speciesLabel(animal.species),
              if (card.breed != null) card.breed!.title,
              if (card.coat != null) card.coat!,
            ].join(' · '),
            style: white.copyWith(fontSize: 16),
          ),
          if (card.breed case final breed?)
            Text('from ${breed.origin}', style: white.copyWith(fontSize: 13)),
          const SizedBox(height: 10),
          Text('Seen $seen ${seen == 1 ? 'time' : 'times'} · discovered by ${card.discoveredBy}',
              style: white.copyWith(fontSize: 13)),
        ],
      ),
    );
  }
}
