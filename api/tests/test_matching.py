"""Re-identification flow with a fake embedder, so each test sets the similarity it needs."""
import pytest

from tests.conftest import BASE_VECTOR, vector_with_similarity
from tests.helpers import FAR, NEARBY, client, fixture, fresh_spot, new_user, post_photo

CAT = fixture("cat_1.jpg")
DOG = fixture("dog_1.jpg")


@pytest.fixture
def mo(fake_embedder):
    """A named cat, discovered by `discoverer` at `spot`."""
    discoverer, spot = new_user(), fresh_spot()
    fake_embedder.queue.append(BASE_VECTOR)
    animal = post_photo(discoverer, CAT, *spot).json()["animal"]
    client.put(f"/animals/{animal['id']}/name", headers=discoverer, json={"name": "Mo"})
    return {"animal": animal, "discoverer": discoverer, "spot": spot}


def near(spot):
    return spot[0] + NEARBY, spot[1]


def test_first_photo_of_an_animal_creates_it_and_the_discoverer_may_name_it(fake_embedder):
    headers = new_user()
    body = post_photo(headers, CAT, *fresh_spot()).json()

    assert body["outcome"] == "new"
    assert body["animal"]["species"] == "cat"
    assert body["animal"]["name"] is None
    assert body["animal"]["sightings_count"] == 1
    assert body["animal"]["can_name"] is True
    assert body["sighting"]["pending"] is False
    assert body["sighting"]["animal"]["id"] == body["animal"]["id"]


def test_name_is_set_once_by_the_discoverer_only(fake_embedder):
    discoverer = new_user()
    animal_id = post_photo(discoverer, CAT, *fresh_spot()).json()["animal"]["id"]
    url = f"/animals/{animal_id}/name"

    assert client.put(url, headers=new_user(), json={"name": "Thief"}).status_code == 403
    assert client.put(url, headers=discoverer, json={"name": "   "}).status_code == 422

    named = client.put(url, headers=discoverer, json={"name": "  Fat Mo "})
    assert named.status_code == 200
    assert named.json()["name"] == "Fat Mo"
    assert named.json()["can_name"] is False

    assert client.put(url, headers=discoverer, json={"name": "Other"}).status_code == 409


def test_confident_match_nearby_links_to_the_known_animal(fake_embedder, mo):
    fake_embedder.queue.append(vector_with_similarity(0.9))
    player = new_user()

    body = post_photo(player, CAT, *near(mo["spot"])).json()

    assert body["outcome"] == "match"
    assert body["animal"]["id"] == mo["animal"]["id"]
    assert body["animal"]["name"] == "Mo"
    assert body["animal"]["sightings_count"] == 2
    assert body["animal"]["can_name"] is False
    assert body["candidates"] == []


def test_same_looking_animal_far_away_is_a_new_one(fake_embedder, mo):
    fake_embedder.queue.append(BASE_VECTOR)
    far_away = (mo["spot"][0] + FAR, mo["spot"][1])

    body = post_photo(new_user(), CAT, *far_away).json()

    assert body["outcome"] == "new"
    assert body["animal"]["id"] != mo["animal"]["id"]


def test_other_species_is_never_matched(fake_embedder, mo):
    fake_embedder.queue.append(BASE_VECTOR)

    body = post_photo(new_user(), DOG, *near(mo["spot"])).json()

    assert body["sighting"]["species"] == "dog"
    assert body["outcome"] == "new"


def test_dissimilar_animal_nearby_is_a_new_one(fake_embedder, mo):
    fake_embedder.queue.append(vector_with_similarity(0.3))

    assert post_photo(new_user(), CAT, *near(mo["spot"])).json()["outcome"] == "new"


def test_uncertain_match_asks_the_player_and_links_on_confirmation(fake_embedder, mo):
    fake_embedder.queue.append(vector_with_similarity(0.6))
    player = new_user()

    body = post_photo(player, CAT, *near(mo["spot"])).json()

    assert body["outcome"] == "uncertain"
    assert body["animal"] is None
    assert body["sighting"]["pending"] is True
    assert [c["animal"]["id"] for c in body["candidates"]] == [mo["animal"]["id"]]
    assert body["candidates"][0]["similarity"] == pytest.approx(0.6)

    sighting_id = body["sighting"]["id"]
    candidates = client.get(f"/sightings/{sighting_id}/candidates", headers=player).json()
    assert [c["animal"]["name"] for c in candidates] == ["Mo"]

    resolved = client.post(
        f"/sightings/{sighting_id}/resolve", headers=player, json={"animal_id": mo["animal"]["id"]}
    ).json()
    assert resolved["outcome"] == "match"
    assert resolved["animal"]["sightings_count"] == 2
    assert resolved["sighting"]["pending"] is False

    again = client.post(f"/sightings/{sighting_id}/resolve", headers=player, json={"animal_id": None})
    assert again.status_code == 409


def test_uncertain_match_can_be_declared_a_new_animal(fake_embedder, mo):
    fake_embedder.queue.append(vector_with_similarity(0.6))
    player = new_user()
    sighting_id = post_photo(player, CAT, *near(mo["spot"])).json()["sighting"]["id"]

    resolved = client.post(f"/sightings/{sighting_id}/resolve", headers=player, json={"animal_id": None}).json()

    assert resolved["outcome"] == "new"
    assert resolved["animal"]["id"] != mo["animal"]["id"]
    assert resolved["animal"]["can_name"] is True  # the player is its discoverer


def test_cannot_link_to_an_animal_that_was_not_a_candidate(fake_embedder, mo):
    elsewhere = post_photo(new_user(), CAT, *fresh_spot()).json()["animal"]["id"]
    fake_embedder.queue.append(vector_with_similarity(0.6))
    player = new_user()
    sighting_id = post_photo(player, CAT, *near(mo["spot"])).json()["sighting"]["id"]

    response = client.post(f"/sightings/{sighting_id}/resolve", headers=player, json={"animal_id": elsewhere})

    assert response.status_code == 422


def test_only_the_author_can_resolve(fake_embedder, mo):
    fake_embedder.queue.append(vector_with_similarity(0.6))
    sighting_id = post_photo(new_user(), CAT, *near(mo["spot"])).json()["sighting"]["id"]

    response = client.post(f"/sightings/{sighting_id}/resolve", headers=new_user(), json={"animal_id": None})

    assert response.status_code == 404


def test_animal_photo_is_visible_to_other_players(fake_embedder, mo):
    response = client.get(f"/animals/{mo['animal']['id']}/photo", headers=new_user())

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


def test_no_response_contains_coordinates(fake_embedder, mo):
    lat, lon = near(mo["spot"])
    fake_embedder.queue.append(vector_with_similarity(0.6))
    player = new_user()
    created = post_photo(player, CAT, lat, lon)
    sighting_id = created.json()["sighting"]["id"]
    responses = [
        created,
        client.get(f"/sightings/{sighting_id}/candidates", headers=player),
        client.post(f"/sightings/{sighting_id}/resolve", headers=player, json={"animal_id": mo["animal"]["id"]}),
        client.get("/sightings/mine", headers=player),
    ]

    for response in responses:
        assert response.status_code in (200, 201), response.text
        for coordinate in (lat, lon, *mo["spot"]):
            assert f"{coordinate:.4f}" not in response.text
        for field in ("lat", "lon", "latitude", "longitude", "location"):
            assert f'"{field}"' not in response.text
