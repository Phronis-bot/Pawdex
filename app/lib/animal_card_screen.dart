import 'package:flutter/material.dart';

import 'api.dart';
import 'photo_view.dart';
import 'rarity.dart';
import 'share_card.dart';
import 'species_label.dart';

void openAnimalCard(BuildContext context, ApiClient api, String animalId) {
  Navigator.push(
    context,
    MaterialPageRoute(builder: (_) => AnimalCardScreen(api: api, animalId: animalId)),
  );
}

class AnimalCardScreen extends StatefulWidget {
  const AnimalCardScreen({super.key, required this.api, required this.animalId});

  final ApiClient api;
  final String animalId;

  @override
  State<AnimalCardScreen> createState() => _AnimalCardScreenState();
}

class _AnimalCardScreenState extends State<AnimalCardScreen> {
  late final Future<AnimalCard> _card = widget.api.animalCard(widget.animalId);

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<AnimalCard>(
      future: _card,
      builder: (context, snapshot) {
        final card = snapshot.data;
        return Scaffold(
          appBar: AppBar(
            title: Text(card == null ? '' : animalTitle(card.animal.name, card.animal.species)),
            actions: [
              if (card != null)
                IconButton(
                  tooltip: 'Share',
                  icon: const Icon(Icons.share),
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => ShareCardScreen(api: widget.api, card: card)),
                  ),
                ),
            ],
          ),
          body: switch (snapshot) {
            AsyncSnapshot(hasError: true) => Center(child: Text('${snapshot.error}')),
            AsyncSnapshot(hasData: false) => const Center(child: CircularProgressIndicator()),
            _ => _CardBody(api: widget.api, card: card!),
          },
        );
      },
    );
  }
}

class _CardBody extends StatelessWidget {
  const _CardBody({required this.api, required this.card});

  final ApiClient api;
  final AnimalCard card;

  @override
  Widget build(BuildContext context) {
    final animal = card.animal;
    final text = Theme.of(context).textTheme;
    final seen = animal.sightingsCount;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        AspectRatio(
          aspectRatio: 1,
          child: ApiPhoto(load: () => api.animalPhoto(animal.id), radius: 16),
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(child: Text(animalTitle(animal.name, animal.species), style: text.headlineMedium)),
            if (animal.rarity case final rarity?) RarityChip(rarity: rarity),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          [
            speciesLabel(animal.species),
            if (card.breed != null) card.breed!.name,
            if (card.coat != null) card.coat!,
          ].join(' · '),
          style: text.titleMedium,
        ),
        const SizedBox(height: 12),
        Text(card.discoveredByMe ? 'Discovered by you' : 'Discovered by ${card.discoveredBy}'),
        Text('Seen $seen ${seen == 1 ? 'time' : 'times'} · first on ${_date(card.chronicle.first.createdAt)}'),
        if (card.breed case final breed?) ...[
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              leading: const Icon(Icons.public),
              title: Text('${breed.name} · from ${breed.origin}'),
              subtitle: Text(breed.history),
            ),
          ),
        ],
        if (card.coatFacts.isNotEmpty) ...[
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.lightbulb_outline),
                      const SizedBox(width: 12),
                      Text('Did you know?', style: text.titleMedium),
                    ],
                  ),
                  for (final fact in card.coatFacts)
                    Padding(
                      padding: const EdgeInsets.only(top: 10),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('•  '),
                          Expanded(child: Text(fact)),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
        const SizedBox(height: 16),
        Text('Chronicle', style: text.titleLarge),
        const SizedBox(height: 8),
        GridView.count(
          crossAxisCount: 3,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 8,
          crossAxisSpacing: 8,
          childAspectRatio: 0.75,
          children: [
            for (final entry in card.chronicle.reversed)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: SizedBox(
                      width: double.infinity,
                      child: ApiPhoto(load: () => api.sightingPhoto(entry.sightingId)),
                    ),
                  ),
                  Text(_date(entry.createdAt), style: text.bodySmall),
                  Text(entry.byMe ? 'by you' : 'by ${entry.by}',
                      style: text.bodySmall, overflow: TextOverflow.ellipsis),
                ],
              ),
          ],
        ),
      ],
    );
  }

  static String _date(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}
