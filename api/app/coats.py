"""Coat colours: detected once per animal with CLIP zero-shot, they set its rarity
and a few short, true facts shown on the card.

Rarity is by coat because it never changes, unlike sighting frequency. Breeds are
handled separately (app/breeds.py) and only when the model is confident.
"""
import enum
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image

from app.breeds import detect_breed
from app.classifier import ZeroShot, get_classifier
from app.models import Animal, Species


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
            "Tabby", "a photo of a striped tabby cat", Rarity.common, (
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
            "Tan", "a photo of a yellow, tan or golden dog", Rarity.common, (
                "Yellow-tan is the most common colour of free-roaming dogs worldwide: it's the coat "
                "dogs tend to end up with when nobody breeds them for looks.",
                "Most of the world's dogs — roughly three in four — are free-ranging 'village dogs', "
                "not pets.",
                "Tan comes from pheomelanin, the same pigment that makes ginger cats ginger.",
            ),
        ),
        "brown": Coat(
            "Brown", "a photo of a brown dog", Rarity.common, (
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
        "black_and_white": Coat(
            "Black and white", "a photo of a black and white dog", Rarity.rare, (
                "White patches come from spotting genes that stop pigment cells from reaching some "
                "areas of skin.",
                "White shows up first on the chest, paws, tail tip and face — the places pigment "
                "cells reach last.",
                "Tiny black freckles that appear in the white areas after birth are called 'ticking'.",
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
            "Grey", "a photo of a grey dog", Rarity.rare, (
                "Grey dogs are usually 'dilute' black — the same gene behind the Weimaraner's silver coat.",
                "Breeders call grey 'blue', as in blue Great Danes and blue Staffies.",
                "Some grey dogs are born black and turn grey as they grow, thanks to a separate "
                "'greying' gene.",
            ),
        ),
        "spotted": Coat(
            "Spotted", "a photo of a spotted dog", Rarity.rare, (
                "Freckle-like spots on a white coat come from a separate 'ticking' gene that paints "
                "colour back in.",
                "Dalmatian puppies are born pure white; their spots appear over the first weeks.",
                "Marbled 'merle' patches are a different gene altogether — the pattern of many "
                "Australian Shepherds.",
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
    clip = get_classifier()
    return ZeroShot(clip.model, clip.processor, [coat.prompt for coat in COATS[species].values()])


def detect_coat(image: Image.Image, species: Species) -> str:
    """The most likely coat key for this species."""
    probs = _coat_zero_shot(species).probs(image)
    return list(COATS[species])[max(range(len(probs)), key=probs.__getitem__)]


def new_animal(image: Image.Image, species: Species, discoverer_id) -> Animal:
    """A freshly discovered animal; coat, rarity and breed come from the discovering photo."""
    coat = detect_coat(image, species)
    breed = detect_breed(image, species)
    return Animal(
        species=species,
        discoverer_id=discoverer_id,
        coat=coat,
        rarity=COATS[species][coat].rarity.value,
        breed=breed[0] if breed else None,
        breed_certainty=breed[1].value if breed else None,
    )
