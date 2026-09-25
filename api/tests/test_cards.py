"""Animal cards: discoverer, coat, rarity, chronicle."""
from pathlib import Path

import pytest

from app.coats import COATS, Rarity, detect_coat
from app.models import Species
from app.photos import load_image
from tests.conftest import BASE_VECTOR, vector_with_similarity
from tests.helpers import NEARBY, client, fixture, fresh_spot, new_user, post_photo

EVAL = Path(__file__).parent.parent / "eval" / "reid"


def nickname(headers) -> str:
    return client.get("/me", headers=headers).json()["nickname"]


def test_every_player_gets_a_stable_nickname():
    headers = new_user()
    first = nickname(headers)

    assert first and " " in first
    assert nickname(headers) == first


def test_coat_table_is_complete():
    for species, coats in COATS.items():
        assert {c.rarity for c in coats.values()} == set(Rarity), species
        for key, coat in coats.items():
            assert coat.label and coat.prompt and len(coat.fact) > 20, key


@pytest.mark.parametrize(
    "path,species,coat",
    [
        ("cat_gladstone/1.jpg", Species.cat, "black"),
        ("cat_palmerston/1.jpg", Species.cat, "black_and_white"),
        ("cat_larry/4.jpg", Species.cat, "tabby_and_white"),
        ("dog_sunny/1.jpg", Species.dog, "black"),
        ("dog_bo/1.jpg", Species.dog, "black_and_white"),
    ],
)
def test_detects_coat_of_known_animals(path, species, coat):
    assert detect_coat(load_image((EVAL / path).read_bytes()), species) == coat


def test_new_animal_gets_coat_and_rarity(fake_embedder):
    body = post_photo(new_user(), fixture("cat_1.jpg"), *fresh_spot()).json()

    assert body["animal"]["rarity"] in {"common", "rare", "legendary"}


def test_card_shows_discoverer_coat_and_chronicle(fake_embedder):
    finder, visitor = new_user(), new_user()
    spot = fresh_spot()
    fake_embedder.queue.append(BASE_VECTOR)
    first = post_photo(finder, fixture("cat_1.jpg"), *spot).json()
    animal_id = first["animal"]["id"]
    client.put(f"/animals/{animal_id}/name", headers=finder, json={"name": "Mo"})
    fake_embedder.queue.append(vector_with_similarity(0.9))
    second = post_photo(visitor, fixture("cat_1.jpg"), spot[0] + NEARBY, spot[1]).json()

    card = client.get(f"/animals/{animal_id}", headers=visitor)
    assert card.status_code == 200
    body = card.json()

    assert body["name"] == "Mo"
    assert body["discovered_by"] == nickname(finder)
    assert body["discovered_by_me"] is False
    assert body["sightings_count"] == 2
    assert body["coat"] == "Ginger"
    assert body["rarity"] == "common"
    assert "male" in body["coat_fact"]
    assert [(e["sighting_id"], e["by"], e["by_me"]) for e in body["chronicle"]] == [
        (first["sighting"]["id"], nickname(finder), False),
        (second["sighting"]["id"], nickname(visitor), True),
    ]
    for field in ("lat", "lon", "latitude", "longitude", "location"):
        assert f'"{field}"' not in card.text
    assert str(spot[0]) not in card.text and str(spot[1]) not in card.text

    # Every chronicle photo can be opened by the visitor.
    for entry in body["chronicle"]:
        assert client.get(f"/sightings/{entry['sighting_id']}/photo", headers=visitor).status_code == 200


def test_animal_created_by_resolve_also_gets_a_coat(fake_embedder):
    spot = fresh_spot()
    fake_embedder.queue.append(BASE_VECTOR)
    post_photo(new_user(), fixture("cat_1.jpg"), *spot)
    fake_embedder.queue.append(vector_with_similarity(0.6))
    player = new_user()
    sighting_id = post_photo(player, fixture("cat_1.jpg"), spot[0] + NEARBY, spot[1]).json()["sighting"]["id"]

    resolved = client.post(f"/sightings/{sighting_id}/resolve", headers=player, json={"animal_id": None}).json()

    card = client.get(f"/animals/{resolved['animal']['id']}", headers=player).json()
    assert card["coat"] == "Ginger"
    assert card["discovered_by_me"] is True


def test_unknown_animal_card_is_404():
    assert client.get("/animals/00000000-0000-0000-0000-000000000000", headers=new_user()).status_code == 404
