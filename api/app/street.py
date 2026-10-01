"""Animals of no recognised breed are shown as local street animals, named the way people
say it where the animal was met (by the country of its first sighting, never the phone's
language), with a few short facts. Only facts we are sure of.
"""
from dataclasses import dataclass

from app.models import Species


@dataclass(frozen=True)
class Street:
    name: str  # "Chó cỏ · local street dog"
    facts: tuple[str, ...]


GENERIC = {Species.dog: "Local street dog", Species.cat: "Local street cat"}

# Country (app/countries.py) -> species -> (local name, what the name means).
LOCAL: dict[str, dict[Species, tuple[str, str]]] = {
    "VN": {
        Species.dog: ("Chó cỏ", "In Vietnamese, 'chó cỏ' — literally 'grass dog' — is the everyday "
                                "name for the local dog of no particular breed."),
        Species.cat: ("Mèo ta", "In Vietnamese, 'mèo ta' — roughly 'our cat' — is the everyday name "
                                "for the local cat of no particular breed."),
    },
    "RU": {
        Species.dog: ("Дворняга", "The Russian 'дворняга' comes from 'двор', a yard: a dog of the yard."),
        Species.cat: ("Дворовый кот", "In Russian, 'дворовый кот' — 'yard cat' — is what people call "
                                      "a cat of no breed."),
    },
}

FACTS = {
    Species.dog: (
        "By common estimates, around three in four of the world's dogs are free-ranging street "
        "and village dogs, not pets.",
        "Many street dogs aren't a mix of breeds at all: genetic studies show village dogs in "
        "Africa and Asia are old local populations, while most breeds are under 200 years old.",
    ),
    Species.cat: (
        "Pedigree cats are a small minority: the vast majority of the world's cats belong to no breed.",
        "All house cats descend from the African wildcat, first living alongside people in the Near "
        "East around 10,000 years ago.",
        "Most cat breeds are younger than 150 years: the first cat show was held at London's "
        "Crystal Palace in 1871.",
    ),
}


def street(species: Species, country: str | None) -> Street:
    local = LOCAL.get(country or "", {}).get(species)
    if local is None:
        return Street(GENERIC[species], FACTS[species])
    name, meaning = local
    return Street(f"{name} · {GENERIC[species].lower()}", (meaning, *FACTS[species][:2]))
