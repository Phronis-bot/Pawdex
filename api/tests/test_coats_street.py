"""Coats: unsure means no coat; the discoverer can fix it. No breed: a local street animal."""
import random

import pytest

from app.config import settings
from app.countries import country_at
from tests.helpers import client, fixture, fresh_spot, new_user, post_photo


def discover(fake_embedder, photo="dog_1.jpg", spot=None):
    player = new_user()
    lat, lon = spot or fresh_spot()
    animal_id = post_photo(player, fixture(photo), lat, lon).json()["animal"]["id"]
    return player, animal_id


def card(player, animal_id):
    return client.get(f"/animals/{animal_id}", headers=player).json()


def test_unsure_coat_shows_nothing_and_counts_as_common(fake_embedder, monkeypatch):
    monkeypatch.setitem(settings.coat_min_confidence, "dog", 1.01)  # never sure
    player, animal_id = discover(fake_embedder)
    c = card(player, animal_id)
    assert c["coat"] is None and c["coat_facts"] == [] and c["rarity"] == "common"


def test_discoverer_fixes_the_coat(fake_embedder):
    player, animal_id = discover(fake_embedder)
    assert {"key": "black_and_tan", "label": "Black and tan"} in card(player, animal_id)["coat_options"]

    fixed = client.put(f"/animals/{animal_id}/coat", headers=player, json={"coat": "merle"})
    assert fixed.status_code == 200
    c = fixed.json()
    assert (c["coat"], c["coat_key"], c["rarity"], c["coat_by_player"]) == ("Merle", "merle", "legendary", True)
    assert any("double merle" in fact for fact in c["coat_facts"])
    assert card(player, animal_id)["coat"] == "Merle"


def test_only_the_discoverer_fixes_the_coat(fake_embedder):
    player, animal_id = discover(fake_embedder)
    other = new_user()
    assert card(other, animal_id)["coat_options"] == []
    assert client.put(f"/animals/{animal_id}/coat", headers=other, json={"coat": "merle"}).status_code == 403
    # A cat coat on a dog.
    assert client.put(f"/animals/{animal_id}/coat", headers=player, json={"coat": "calico"}).status_code == 422


@pytest.mark.parametrize(
    "lat,lon,country",
    [(15.88, 108.33, "VN"), (55.75, 37.62, "RU"), (54.71, 20.51, "RU"), (41.01, 28.98, None), (13.75, 100.5, None)],
)
def test_country_at(lat, lon, country):
    assert country_at(lat, lon) == country


def test_street_names_follow_the_country_of_the_sighting(fake_embedder):
    # dog_3 is a Hoi An street dog: no breed.
    player, animal_id = discover(fake_embedder, "dog_3.jpg")  # around Ho Chi Minh City
    c = card(player, animal_id)
    assert c["breed"] is None
    assert c["street"]["name"] == "Chó cỏ · local street dog"
    assert "grass dog" in c["street"]["facts"][0]

    istanbul = (41.0 + random.random() * 0.05, 28.9 + random.random() * 0.05)
    player, animal_id = discover(fake_embedder, "dog_3.jpg", istanbul)
    c = card(player, animal_id)
    assert c["street"]["name"] == "Local street dog"
    assert len(c["street"]["facts"]) >= 2
