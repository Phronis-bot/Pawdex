"""Finding the animal: crop for re-identification, blurred background for privacy."""
import io
from pathlib import Path

import pytest
from PIL import Image, ImageFilter, ImageOps, ImageStat

from app.models import Species
from app.photos import load_image
from app.segment import blur_background, crop_to_animal, find_animal
from tests.helpers import client, fixture, fresh_spot, new_user, post_photo

EVAL = Path(__file__).parent.parent / "eval"


def sharpness(image: Image.Image, where: Image.Image) -> float:
    """Mean edge strength inside the `where` mask: blurring drives it towards zero."""
    return ImageStat.Stat(image.convert("L").filter(ImageFilter.FIND_EDGES), where).mean[0]


def masks(region, size):
    """(animal, background) masks, each shrunk away from the soft border between them."""
    animal = region.mask.resize(size).point(lambda v: 255 if v > 127 else 0)
    background = ImageOps.invert(animal)
    edge = max(5, size[0] // 40) | 1
    return animal.filter(ImageFilter.MinFilter(edge)), background.filter(ImageFilter.MinFilter(edge * 3))


@pytest.mark.parametrize(
    "name,species", [("cat_1.jpg", Species.cat), ("cat_3.jpg", Species.cat), ("dog_3.jpg", Species.dog)]
)
def test_finds_the_animal(name, species):
    image = load_image(fixture(name))
    region = find_animal(image, species)

    assert region is not None
    left, top, right, bottom = region.box
    assert 0 <= left < right <= image.width and 0 <= top < bottom <= image.height
    assert region.mask.size == image.size


def test_does_not_find_the_other_species():
    assert find_animal(load_image(fixture("dog_3.jpg")), Species.cat) is None


def test_crop_is_mostly_the_animal():
    image = load_image(fixture("dog_3.jpg"))  # a small dog in a big empty street
    crop = crop_to_animal(image, find_animal(image, Species.dog))

    assert crop.width * crop.height < 0.4 * image.width * image.height


def test_blur_changes_the_background_not_the_animal():
    image = load_image((EVAL / "reid" / "cat_palmerston" / "2.jpg").read_bytes())  # a man behind the cat
    region = find_animal(image, Species.cat)
    blurred = blur_background(image, region)
    animal, background = masks(region, image.size)

    assert sharpness(blurred, background) < 0.3 * sharpness(image, background)
    assert sharpness(blurred, animal) > 0.9 * sharpness(image, animal)


def test_stored_photo_has_a_blurred_background(fake_embedder):
    original = (EVAL / "reid" / "cat_palmerston" / "2.jpg").read_bytes()
    player = new_user()
    sighting = post_photo(player, original, *fresh_spot()).json()["sighting"]

    stored = Image.open(io.BytesIO(client.get(f"/sightings/{sighting['id']}/photo", headers=player).content))
    image = load_image(original).resize(stored.size)
    _, background = masks(find_animal(image, Species.cat), stored.size)

    assert sharpness(stored, background) < 0.3 * sharpness(image, background)
