"""Coat colours: detected once per animal with CLIP zero-shot, they set its rarity
and a short, true fact shown on the card.

Rarity is by coat because it never changes, unlike sighting frequency. We do not
guess breeds: street animals are almost always mixed.
"""
import enum
from dataclasses import dataclass

import torch
from PIL import Image

from app.breeds import detect_breed
from app.classifier import get_classifier
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
    fact: str


COATS: dict[Species, dict[str, Coat]] = {
    Species.cat: {
        "tabby": Coat(
            "Tabby", "a photo of a striped tabby cat", Rarity.common,
            "The striped tabby coat is the oldest cat pattern: the African wildcat, "
            "ancestor of every house cat, wears it too. Look for the 'M' on the forehead.",
        ),
        "tabby_and_white": Coat(
            "Tabby and white", "a photo of a tabby and white cat with a white chest and paws", Rarity.common,
            "Tabby-and-white combines two separate genes: one draws the stripes, "
            "another keeps pigment away from the chest, paws and face.",
        ),
        "orange": Coat(
            "Ginger", "a photo of an orange ginger cat", Rarity.common,
            "About four in five ginger cats are male: the orange gene sits on the X chromosome.",
        ),
        "black_and_white": Coat(
            "Tuxedo", "a photo of a black and white cat", Rarity.common,
            "'Tuxedo' is a pattern, not a breed: white-spotting genes stop pigment cells "
            "from reaching parts of the body.",
        ),
        "black": Coat(
            "Black", "a photo of a solid black cat", Rarity.rare,
            "A black cat's fur can 'rust' to reddish brown after lots of time in the sun.",
        ),
        "grey": Coat(
            "Grey", "a photo of a solid grey cat", Rarity.rare,
            "Grey is 'dilute' black: one gene spreads the pigment more thinly, turning black into blue-grey.",
        ),
        "white": Coat(
            "White", "a photo of a solid white cat", Rarity.rare,
            "White cats with blue eyes are often deaf: the gene for white fur also affects the inner ear.",
        ),
        "colorpoint": Coat(
            "Colour-point", "a photo of a siamese colorpoint cat", Rarity.rare,
            "Colour-points have a heat-sensitive pigment enzyme: colour only develops on the "
            "cooler parts of the body — ears, face, paws and tail.",
        ),
        "calico": Coat(
            "Calico", "a photo of a calico cat with orange, black and white patches", Rarity.legendary,
            "Calico cats are almost always female. A male calico needs an extra X chromosome — "
            "roughly one in three thousand.",
        ),
        "tortoiseshell": Coat(
            "Tortoiseshell", "a photo of a tortoiseshell cat with mottled black and orange fur", Rarity.legendary,
            "Tortoiseshells, like calicos, are almost always female: black and orange genes "
            "sit on the two X chromosomes.",
        ),
    },
    Species.dog: {
        "tan": Coat(
            "Tan", "a photo of a yellow, tan or golden dog", Rarity.common,
            "Yellow-tan is the most common colour of free-roaming dogs worldwide: it's the coat "
            "dogs tend to end up with when nobody breeds them for looks.",
        ),
        "brown": Coat(
            "Brown", "a photo of a brown dog", Rarity.common,
            "True brown ('liver') is recessive: a dog needs two copies, which also makes its nose brown instead of black.",
        ),
        "black": Coat(
            "Black", "a photo of a solid black dog", Rarity.common,
            "Solid black is usually dominant in dogs: one copy of the 'dominant black' gene is enough.",
        ),
        "black_and_white": Coat(
            "Black and white", "a photo of a black and white dog", Rarity.rare,
            "White patches come from spotting genes that stop pigment cells from reaching some areas of skin.",
        ),
        "white": Coat(
            "White", "a photo of a white dog", Rarity.rare,
            "Most white dogs aren't albino: they carry spotting genes turned all the way up, "
            "which is why their noses and eyes stay dark.",
        ),
        "grey": Coat(
            "Grey", "a photo of a grey dog", Rarity.rare,
            "Grey dogs are usually 'dilute' black — the same gene behind the Weimaraner's silver coat.",
        ),
        "spotted": Coat(
            "Spotted", "a photo of a spotted dog", Rarity.rare,
            "Freckle-like spots on a white coat come from a separate 'ticking' gene that paints colour back in.",
        ),
        "brindle": Coat(
            "Brindle", "a photo of a brindle dog with tiger stripes", Rarity.legendary,
            "Brindle's tiger stripes come from a variant of the same gene that can make a dog solid black.",
        ),
    },
}


@torch.inference_mode()
def detect_coat(image: Image.Image, species: Species) -> str:
    """The most likely coat key for this species."""
    clip = get_classifier()
    keys = list(COATS[species])
    inputs = clip.processor(
        text=[COATS[species][k].prompt for k in keys], images=image, return_tensors="pt", padding=True
    )
    probs = clip.model(**inputs).logits_per_image.softmax(dim=-1)[0]
    return keys[int(probs.argmax())]


def new_animal(image: Image.Image, species: Species, discoverer_id) -> Animal:
    """A freshly discovered animal; coat, rarity and breed come from the discovering photo."""
    coat = detect_coat(image, species)
    return Animal(
        species=species,
        discoverer_id=discoverer_id,
        coat=coat,
        rarity=COATS[species][coat].rarity.value,
        breed=detect_breed(image, species),
    )
