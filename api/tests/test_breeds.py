"""Breeds: shown only when confident, only on the card, and never affecting rarity."""
from pathlib import Path

import h3
import pytest

from app.breeds import BREEDS, MIXED_PROMPTS, WIKIDATA, Certainty, decide_breed, decide_head_breed, detect_breed
from app.coats import animal_crop
from app.config import settings
from app.models import Species
from app.photos import load_image
from tests.conftest import BASE_VECTOR, vector_with_similarity
from tests.helpers import NEARBY, client, fixture, fresh_spot, new_user, post_photo

EVAL = Path(__file__).parent.parent / "eval"


def test_breed_table_is_complete():
    for species, breeds in BREEDS.items():
        assert MIXED_PROMPTS[species]
        for key, breed in breeds.items():
            assert breed.label and breed.origin and len(breed.history) > 30, key
            assert len(breed.relatives) > 20, key
            assert len(breed.facts) >= 2 and all(len(f) > 15 for f in breed.facts), key


@pytest.mark.parametrize(
    "path,species,breed",
    [
        ("breeds/dog_labrador/2.jpg", Species.dog, "labrador"),
        ("breeds/dog_corgi/1.jpg", Species.dog, "corgi"),
        ("breeds/dog_kangal/1.jpg", Species.dog, "kangal"),
        ("breeds/cat_persian/2.jpg", Species.cat, "persian"),
        ("breeds/cat_sphynx/1.jpg", Species.cat, "sphynx"),
        ("breeds/cat_maine_coon/3.jpg", Species.cat, "maine_coon"),
    ],
)
def test_recognises_clear_purebreds(path, species, breed):
    image = animal_crop(load_image((EVAL / path).read_bytes()), species)
    assert detect_breed(image, species) == (breed, Certainty.confirmed)


@pytest.mark.parametrize(
    "path,species",
    [
        ("breeds/dog_mixed/1.jpg", Species.dog),
        ("breeds/dog_mixed/7.jpg", Species.dog),
        ("breeds/cat_mixed/4.jpg", Species.cat),
        ("reid/cat_larry/6.jpg", Species.cat),
    ],
)
def test_street_animals_stay_mixed(path, species):
    image = animal_crop(load_image((EVAL / path).read_bytes()), species)
    assert detect_breed(image, species) is None


def test_breed_is_on_the_card_only(fake_embedder):
    player = new_user()
    lat, lon = fresh_spot()
    fake_embedder.queue.append(BASE_VECTOR)
    labrador = (EVAL / "breeds" / "dog_labrador" / "2.jpg").read_bytes()
    created = post_photo(player, labrador, lat, lon)
    animal_id = created.json()["animal"]["id"]

    card = client.get(f"/animals/{animal_id}", headers=player).json()
    assert card["breed"]["name"] == "Labrador Retriever"
    assert card["breed"]["certain"] is True
    assert "Newfoundland" in card["breed"]["history"]
    assert "Golden" in card["breed"]["relatives"]
    assert len(card["breed"]["facts"]) == 2

    # Nowhere else: not in the upload result, the map, the zone list or as a candidate.
    fake_embedder.queue.append(vector_with_similarity(0.6))
    uncertain = post_photo(new_user(), labrador, lat + NEARBY, lon)
    cell = h3.latlng_to_cell(lat, lon, settings.map_cell_resolution)
    for response in (
        created,
        uncertain,
        client.get("/map/zones", headers=player, params={"lat": lat, "lon": lon}),
        client.get(f"/map/zones/{cell}/animals", headers=player),
        client.get("/sightings/mine", headers=player),
    ):
        assert "breed" not in response.text
        assert "Labrador" not in response.text


def test_street_dog_card_has_no_breed(fake_embedder):
    player = new_user()
    animal_id = post_photo(player, fixture("dog_3.jpg"), *fresh_spot()).json()["animal"]["id"]

    assert client.get(f"/animals/{animal_id}", headers=player).json()["breed"] is None


@pytest.mark.parametrize(
    "species,top,mixed,expected",
    [
        (Species.cat, 0.85, 0.05, ("siamese", Certainty.confirmed)),
        # Shishka: the model said Siamese 0.71 - below "confirmed" for cats, but not unknown.
        (Species.cat, 0.71, 0.00, ("siamese", Certainty.likely)),
        (Species.cat, 0.55, 0.05, None),
        (Species.dog, 0.45, 0.10, ("siamese", Certainty.likely)),
        # "Mixed breed" always wins ties and beats a stronger-looking breed.
        (Species.cat, 0.90, 0.95, None),
    ],
)
def test_three_levels_of_certainty(species, top, mixed, expected):
    assert decide_breed([("siamese", top), ("birman", 0.01)], mixed, species) == expected


def test_every_cat_breed_is_known_to_the_head():
    assert set(WIKIDATA[Species.cat]) == set(BREEDS[Species.cat])


@pytest.mark.parametrize(
    "probs,mixed,expected",
    [
        ({"bengal": 0.95, "mixed": 0.05}, 0.0, ("bengal", Certainty.confirmed)),
        ({"bengal": 0.75, "mixed": 0.25}, 0.0, ("bengal", Certainty.likely)),
        ({"bengal": 0.60, "mixed": 0.40}, 0.0, None),
        # Zero-shot thinks it's a street cat: no breed, however sure the head is.
        ({"bengal": 0.99, "mixed": 0.01}, 0.5, None),
        ({"mixed": 0.9, "bengal": 0.1}, 0.0, None),
        # Split between Siamese look-alikes: "Looks like a Siamese".
        ({"tonkinese": 0.45, "thai": 0.3, "mixed": 0.25}, 0.0, ("siamese", Certainty.likely)),
        # A breed the head knows but we have no card for is never shown.
        ({"Q17517549": 0.95, "mixed": 0.05}, 0.0, None),
    ],
)
def test_head_decision(probs, mixed, expected):
    assert decide_head_breed(probs, mixed, Species.cat) == expected
