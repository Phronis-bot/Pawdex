"""Coat colours: detected once per animal with CLIP zero-shot, they set its rarity
and a few short, true facts shown on the card.

Rarity is by coat because it never changes, unlike sighting frequency. Breeds are
handled separately (app/breeds.py) and only when the model is confident.
"""
import enum
from dataclasses import dataclass
from functools import lru_cache

import torch
from PIL import Image

from app.breeds import _breed_clip, detect_breed
from app.classifier import ZeroShot
from app.config import settings
from app.models import Animal, Species
from app.segment import crop_to_animal, find_animal


class Rarity(str, enum.Enum):
    common = "common"
    rare = "rare"
    legendary = "legendary"


@dataclass(frozen=True)
class Coat:
    label: str  # shown to players
    prompt: str  # CLIP zero-shot prompt
    rarity: Rarity
    facts: tuple[str, ...]


COATS: dict[Species, dict[str, Coat]] = {
    Species.cat: {
        "tabby": Coat(
            "Tabby", "a photo of a tabby cat with stripes or spots", Rarity.common, (
                "The striped tabby coat is the oldest cat pattern: the African wildcat, ancestor of "
                "every house cat, wears it too.",
                "Almost every tabby has a letter 'M' drawn on its forehead.",
                "Tabby is a pattern, not a breed, and comes in four styles: mackerel (thin stripes), "
                "classic (swirls), spotted and ticked.",
            ),
        ),
        "tabby_and_white": Coat(
            "Tabby and white", "a photo of a tabby and white cat with a white chest and paws", Rarity.common, (
                "Two separate genes are at work: one draws the stripes, another keeps pigment away "
                "from parts of the body.",
                "White appears on the belly, chest and paws because pigment cells travel down from "
                "the spine as a kitten develops and don't reach everywhere.",
                "Larry, Chief Mouser at 10 Downing Street, is a tabby-and-white former stray adopted "
                "from a London shelter in 2011.",
            ),
        ),
        "orange": Coat(
            "Ginger", "a photo of an orange ginger cat", Rarity.common, (
                "About four in five ginger cats are male: the orange gene sits on the X chromosome.",
                "The colour comes from pheomelanin, the same pigment behind red hair in people.",
                "Ginger cats are almost never truly solid: look closely and you'll find at least "
                "faint tabby stripes.",
            ),
        ),
        "black_and_white": Coat(
            "Tuxedo", "a photo of a black and white cat", Rarity.common, (
                "'Tuxedo' is a pattern, not a breed: white-spotting genes stop pigment cells from "
                "reaching parts of the body.",
                "White always starts at the chest and paws, which is why so many look dressed in a "
                "shirt front and socks.",
                "Cartoon stars Sylvester and Felix the Cat are both black-and-white cats.",
            ),
        ),
        "black": Coat(
            "Black", "a photo of a solid black cat", Rarity.rare, (
                "A black cat's fur can 'rust' to reddish brown after lots of time in the sun.",
                "Black cats are tabbies in disguise: in bright light you can sometimes see faint "
                "'ghost' stripes.",
                "In Britain and Japan, a black cat is traditionally a sign of good luck.",
            ),
        ),
        "grey": Coat(
            "Grey", "a photo of a solid grey cat", Rarity.rare, (
                "Grey is 'dilute' black: one gene spreads the pigment more thinly, turning black "
                "into blue-grey.",
                "Cat breeders don't say grey — they call this colour 'blue'.",
                "The same dilution gene turns ginger into soft cream.",
            ),
        ),
        "chocolate": Coat(
            "Chocolate", "a photo of a solid chocolate brown cat", Rarity.rare, (
                "True chocolate brown is rare in cats: it needs two copies of a recessive gene, which is "
                "why you seldom see it outside pedigree breeds.",
                "The same brown gene, diluted, gives the soft lilac (lavender) colour.",
                "The old Thai Tamra Maew poems already describe a solid brown cat, the 'Suphalak'.",
            ),
        ),
        "white": Coat(
            "White", "a photo of a solid white cat", Rarity.rare, (
                "White cats with blue eyes are often deaf: the gene for white fur also affects the inner ear.",
                "An odd-eyed white cat, with one blue eye, is often deaf only on the blue-eyed side.",
                "White hides the real colour underneath: many white kittens are born with a small "
                "coloured smudge on the head that fades as they grow.",
            ),
        ),
        "colorpoint": Coat(
            "Colour-point", "a photo of a siamese colorpoint cat", Rarity.rare, (
                "A heat-sensitive pigment enzyme colours only the cooler parts of the body — ears, "
                "face, paws and tail.",
                "Colour-point kittens are born almost white and darken as they grow.",
                "Shave a patch of fur and it may grow back darker, because the bare skin is cooler.",
            ),
        ),
        "calico": Coat(
            "Calico", "a photo of a calico cat with orange, black and white patches", Rarity.legendary, (
                "Calico cats are almost always female. A male calico needs an extra X chromosome — "
                "roughly one in three thousand.",
                "The patches are random: in each patch a different X chromosome is switched off. "
                "The first cloned cat, CC (2001), looked nothing like her calico 'mother'.",
                "In Japan calicos are called 'mi-ke' and are considered lucky; many maneki-neko "
                "beckoning-cat figures are calicos.",
            ),
        ),
        "tortoiseshell": Coat(
            "Tortoiseshell", "a photo of a tortoiseshell cat with mottled black and orange fur", Rarity.legendary, (
                "Tortoiseshells, like calicos, are almost always female: black and orange genes sit "
                "on the two X chromosomes.",
                "No two 'torties' are alike — the mix of black and orange is decided cell by cell "
                "before birth.",
                "Owners joke about 'tortitude', a fiery temper; a small 2015 survey of owners "
                "hinted at it, but science hasn't settled it.",
            ),
        ),
    },
    Species.dog: {
        "tan": Coat(
            "Tan", "a photo of a yellow, tan or reddish dog", Rarity.common, (
                "Yellow-tan is the most common colour of free-roaming dogs worldwide: it's the coat "
                "dogs tend to end up with when nobody breeds them for looks.",
                "Most of the world's dogs — roughly three in four — are free-ranging 'village dogs', "
                "not pets.",
                "Tan comes from pheomelanin, the same pigment that makes ginger cats ginger.",
            ),
        ),
        "cream": Coat(
            "Cream", "a photo of a pale cream coloured dog", Rarity.common, (
                "Cream is a pale form of the same red-yellow pigment that makes tan and red dogs.",
                "Separate genes set how intense that pigment is, so one litter can range from cream "
                "to deep red.",
                "Unlike a true albino, a cream dog keeps a dark nose and dark eyes.",
            ),
        ),
        "brown": Coat(
            "Brown", "a photo of a solid brown dog", Rarity.common, (
                "True brown ('liver') is recessive: a dog needs two copies, which also makes its "
                "nose brown instead of black.",
                "Chocolate Labradors get their colour from this same gene.",
                "Brown dogs often have light amber eyes: the gene lightens the eyes too.",
            ),
        ),
        "black": Coat(
            "Black", "a photo of a solid black dog", Rarity.common, (
                "Solid black is usually dominant in dogs: one copy of the 'dominant black' gene is enough.",
                "Black wolves in North America got their colour from dogs: the gene passed from "
                "dogs into wolves long ago.",
                "Many black dogs have a small white star on the chest — a trace of white-spotting genes.",
            ),
        ),
        "black_and_tan": Coat(
            "Black and tan",
            "a photo of a black and tan dog, black with tan markings on the face, chest and legs",
            Rarity.common, (
                "The tan always sits in the same places: dots above the eyes, the muzzle, chest, legs "
                "and under the tail.",
                "One gene variant draws this pattern, on Rottweilers, Dobermanns and street dogs alike.",
                "The Black and Tan Coonhound, an American hunting breed, is named after its coat.",
            ),
        ),
        "bicolor": Coat(
            "Bicolour", "a photo of a two-coloured dog with large white patches", Rarity.common, (
                "White patches come from spotting genes that stop pigment cells from reaching some "
                "areas of skin.",
                "White shows up first on the chest, paws, tail tip and face — the places pigment "
                "cells reach last.",
                "Tiny dark freckles that appear in the white areas after birth are called 'ticking'.",
            ),
        ),
        "white": Coat(
            "White", "a photo of a white dog", Rarity.rare, (
                "Most white dogs aren't albino: they carry spotting genes turned all the way up, "
                "which is why their noses and eyes stay dark.",
                "Like white cats, mostly-white dogs are more often deaf in one or both ears.",
                "Shepherds favoured white guardian dogs so they could tell dog from wolf in the dark.",
            ),
        ),
        "grey": Coat(
            "Grey", "a photo of a solid grey dog", Rarity.rare, (
                "Grey dogs are usually 'dilute' black — the same gene behind the Weimaraner's silver coat.",
                "Breeders call grey 'blue', as in blue Great Danes and blue Staffies.",
                "Some grey dogs are born black and turn grey as they grow, thanks to a separate "
                "'greying' gene.",
            ),
        ),
        "tricolor": Coat(
            "Tricolour", "a photo of a tricolor dog with black, tan and white patches", Rarity.rare, (
                "A tricolour dog is usually black and tan with white patches added: two separate "
                "genes at work.",
                "It's the classic colouring of Beagles and Bernese Mountain Dogs.",
                "The tan keeps to its usual spots — eyebrows, cheeks and legs — while the white can "
                "appear almost anywhere.",
            ),
        ),
        "spotted": Coat(
            "Spotted", "a photo of a white dog with small black spots, like a dalmatian", Rarity.rare, (
                "Freckle-like spots on a white coat come from a separate 'ticking' gene that paints "
                "colour back in.",
                "Dalmatian puppies are born pure white; their spots appear over the first weeks.",
                "Ticking can be so dense that a white dog looks grey or roan, as in Australian Cattle Dogs.",
            ),
        ),
        "merle": Coat(
            "Merle", "a photo of a merle dog with a marbled grey and black coat", Rarity.legendary, (
                "Merle is a marbled pattern: patches of full colour scattered over a lighter, diluted coat.",
                "It's the signature coat of Australian Shepherds, Border Collies and Catahoula dogs.",
                "Breeders never pair two merles: 'double merle' puppies are often deaf or blind.",
            ),
        ),
        "brindle": Coat(
            "Brindle", "a photo of a brindle dog with tiger stripes", Rarity.legendary, (
                "Brindle's tiger stripes come from a variant of the same gene that can make a dog solid black.",
                "Brindle is a classic colour of Greyhounds, Boxers and Mastiffs.",
                "Like a tiger's, no two brindle coats have the same stripes.",
            ),
        ),
    },
}


@lru_cache
def _coat_zero_shot(species: Species) -> ZeroShot:
    # The large breed CLIP: on the Commons coat test set (eval/coat_eval.py) it beat the base
    # one, and the photo's features are computed once for both coat and breed.
    model, processor = _breed_clip()
    return ZeroShot(model, processor, [coat.prompt for coat in COATS[species].values()])


def detect_coat(image: Image.Image, species: Species, features: torch.Tensor | None = None) -> str | None:
    """The most likely coat key for this species, or None when the model isn't sure enough:
    then the card shows no coat and no coat facts, rather than wrong ones. `image` should be
    cropped to the animal; `features` are its breed-CLIP features, if already computed."""
    probs = _coat_zero_shot(species).probs(image, features)
    best = max(range(len(probs)), key=probs.__getitem__)
    if probs[best] < settings.coat_min_confidence[species.value]:
        return None
    return list(COATS[species])[best]


def rarity_of(species: Species, coat: str | None) -> str:
    """Rarity is by coat; an unknown coat counts as an ordinary one."""
    return (COATS[species][coat].rarity if coat else Rarity.common).value


def animal_crop(image: Image.Image, species: Species) -> Image.Image:
    region = find_animal(image, species)
    return crop_to_animal(image, region) if region else image


def new_animal(
    image: Image.Image, species: Species, discoverer_id, subject: Image.Image | None = None,
    country: str | None = None,
) -> Animal:
    """A freshly discovered animal; coat, rarity and breed come from the discovering photo.

    `subject` is the animal cropped out of it (app.segment.prepare_photo), found here if not
    given: the breed classifier was trained on cropped animals.
    """
    subject = subject or animal_crop(image, species)
    features = _coat_zero_shot(species).image_features(subject)
    coat = detect_coat(subject, species, features)
    breed = detect_breed(subject, species, features)
    return Animal(
        species=species,
        discoverer_id=discoverer_id,
        country=country,
        coat=coat,
        rarity=rarity_of(species, coat),
        breed=breed.key if breed else None,
        breed_certainty=breed.certainty.value if breed else None,
        breed_alt=breed.alt if breed else None,
    )
