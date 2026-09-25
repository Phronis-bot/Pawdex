import 'api.dart';

String speciesLabel(Species species) => switch (species) {
      Species.cat => 'Cat',
      Species.dog => 'Dog',
    };
