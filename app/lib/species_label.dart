import 'api.dart';

String speciesLabel(Species species) => switch (species) {
      Species.cat => 'Cat',
      Species.dog => 'Dog',
    };

/// "cat" / "dog", for use inside sentences.
String speciesWord(Species species) => speciesLabel(species).toLowerCase();

String animalTitle(String? name, Species species) => name ?? 'Unnamed ${speciesWord(species)}';
