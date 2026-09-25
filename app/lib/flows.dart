import 'package:flutter/material.dart';

import 'api.dart';
import 'confirm_screen.dart';
import 'name_screen.dart';

typedef FinalAnimal = ({Outcome outcome, Animal animal});

/// After an upload: ask "which one is it?" if the server wasn't sure, then offer
/// naming to the discoverer. Returns null if the player backed out of confirming.
Future<FinalAnimal?> completeSighting(
  BuildContext context,
  ApiClient api,
  SightingResult result,
) async {
  var outcome = result.outcome;
  var animal = result.animal;

  if (outcome == Outcome.uncertain) {
    final resolved = await Navigator.push<SightingResult>(
      context,
      MaterialPageRoute(
        builder: (_) => ConfirmScreen(api: api, sighting: result.sighting, candidates: result.candidates),
      ),
    );
    if (resolved == null) return null;
    outcome = resolved.outcome;
    animal = resolved.animal;
  }

  if (animal!.canName && context.mounted) {
    animal = await askName(context, api, animalId: animal.id, species: animal.species) ?? animal;
  }
  return (outcome: outcome, animal: animal);
}

Future<Animal?> askName(
  BuildContext context,
  ApiClient api, {
  required String animalId,
  required Species species,
}) {
  return Navigator.push<Animal>(
    context,
    MaterialPageRoute(builder: (_) => NameScreen(api: api, animalId: animalId, species: species)),
  );
}
