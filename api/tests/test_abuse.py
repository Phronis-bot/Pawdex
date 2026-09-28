"""Upload limits and photo reports."""
import pytest

from app.config import settings
from app.ratelimit import ip_uploads
from tests.conftest import BASE_VECTOR, vector_with_similarity
from tests.helpers import NEARBY, client, fixture, fresh_spot, new_user, post_photo

pytestmark = pytest.mark.usefixtures("fake_embedder")

CAT = fixture("cat_1.jpg")


@pytest.fixture
def limits(monkeypatch):
    ip_uploads.reset()
    yield lambda per_user, per_ip: (
        monkeypatch.setattr(settings, "uploads_per_user_per_hour", per_user),
        monkeypatch.setattr(settings, "uploads_per_ip_per_hour", per_ip),
    )
    ip_uploads.reset()


def test_player_upload_limit(limits):
    limits(2, 1000)
    player = new_user()

    assert post_photo(player, CAT, *fresh_spot()).status_code == 201
    assert post_photo(player, CAT, *fresh_spot()).status_code == 201
    blocked = post_photo(player, CAT, *fresh_spot())

    assert blocked.status_code == 429
    assert post_photo(new_user(), CAT, *fresh_spot()).status_code == 201  # others are fine


def test_ip_upload_limit_stops_throwaway_ids(limits):
    limits(1000, 2)

    assert post_photo(new_user(), CAT, *fresh_spot()).status_code == 201
    assert post_photo(new_user(), CAT, *fresh_spot()).status_code == 201
    assert post_photo(new_user(), CAT, *fresh_spot()).status_code == 429


@pytest.fixture
def shared_animal(fake_embedder):
    """An animal seen by its discoverer and then by a second player."""
    finder, visitor = new_user(), new_user()
    spot = fresh_spot()
    fake_embedder.queue.append(BASE_VECTOR)
    first = post_photo(finder, CAT, *spot).json()
    fake_embedder.queue.append(vector_with_similarity(0.95))
    second = post_photo(visitor, CAT, spot[0] + NEARBY, spot[1]).json()
    return {
        "animal_id": first["animal"]["id"],
        "finder_photo": first["sighting"]["id"],
        "visitor": visitor,
        "visitor_photo": second["sighting"]["id"],
    }


def report(headers, sighting_id, reason="person_visible"):
    return client.post(f"/sightings/{sighting_id}/report", headers=headers, json={"reason": reason})


def test_enough_reports_hide_a_photo_from_everyone_but_its_author(shared_animal):
    photo, author = shared_animal["visitor_photo"], shared_animal["visitor"]
    reporters = [new_user() for _ in range(settings.reports_to_hide)]

    for i, reporter in enumerate(reporters):
        assert report(reporter, photo).status_code == 204
        still_visible = i + 1 < settings.reports_to_hide
        assert (client.get(f"/sightings/{photo}/photo", headers=new_user()).status_code == 200) == still_visible

    stranger = new_user()
    card = client.get(f"/animals/{shared_animal['animal_id']}", headers=stranger).json()
    assert photo not in [e["sighting_id"] for e in card["chronicle"]]
    assert client.get(f"/sightings/{photo}/photo", headers=author).status_code == 200
    own_card = client.get(f"/animals/{shared_animal['animal_id']}", headers=author).json()
    assert photo in [e["sighting_id"] for e in own_card["chronicle"]]


def test_one_player_cannot_hide_a_photo_alone(shared_animal):
    photo, reporter = shared_animal["visitor_photo"], new_user()

    for _ in range(settings.reports_to_hide + 2):
        assert report(reporter, photo).status_code == 204

    assert client.get(f"/sightings/{photo}/photo", headers=new_user()).status_code == 200


def test_cannot_report_own_photo_or_with_unknown_reason(shared_animal):
    photo = shared_animal["visitor_photo"]

    assert report(shared_animal["visitor"], photo).status_code == 404
    assert report(new_user(), photo, reason="i_dont_like_cats").status_code == 422
