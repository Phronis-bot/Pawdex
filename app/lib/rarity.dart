import 'package:flutter/material.dart';

import 'api.dart';

extension RarityStyle on Rarity {
  String get label => switch (this) {
        Rarity.common => 'Common',
        Rarity.rare => 'Rare',
        Rarity.legendary => 'Legendary',
      };

  Color get color => switch (this) {
        Rarity.common => const Color(0xFF7D8590),
        Rarity.rare => const Color(0xFF2E7DD7),
        Rarity.legendary => const Color(0xFFD99A00),
      };

  int get stars => index + 1;
}

class RarityChip extends StatelessWidget {
  const RarityChip({super.key, required this.rarity});

  final Rarity rarity;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: rarity.color, borderRadius: BorderRadius.circular(20)),
      child: Text(
        '${'★' * rarity.stars} ${rarity.label}',
        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
      ),
    );
  }
}
