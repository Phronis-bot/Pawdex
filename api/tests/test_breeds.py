"""Breeds: shown only when confident, only on the card, and never affecting rarity."""
from pathlib import Path

import h3
import pytest

from app.breeds import BREEDS, MIXED_PROMPTS, detect_breed
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
        ("breeds/cat_siamese/2.jpg", Species.cat, "siamese"),
        ("breeds/cat_sphynx/2.jpg", Species.cat, "sphynx"),
        ("breeds/cat_maine_coon/3.jpg", Species.cat, "maine_coon"),
    ],
)
def test_recognises_clear_purebreds(path, species, breed):
    assert detect_breed(load_image((EVAL / path).read_bytes()), species) == breed


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
    assert detect_breed(load_image((EVAL / path).read_bytes()), species) is None


def test_breed_is_on_the_card_only(fake_embedder):
    player = new_user()
    lat, lon = fresh_spot()
    fake_embedder.queue.append(BASE_VECTOR)
    labrador = (EVAL / "breeds" / "dog_labrador" / "2.jpg").read_bytes()
    created = post_photo(player, labrador, lat, lon)
    animal_id = created.json()["animal"]["id"]

    card = client.get(f"/animals/{animal_id}", headers=player).json()
    assert card["breed"]["name"] == "Labrador Retriever"
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
