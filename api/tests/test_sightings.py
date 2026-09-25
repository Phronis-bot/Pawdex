import io
import os
from pathlib import Path

import pytest
from PIL import Image

from tests.helpers import client, fixture, fresh_spot, new_user, post_photo

pytestmark = pytest.mark.usefixtures("fake_embedder")

STORAGE_DIR = Path(os.environ["PAWDEX_STORAGE_DIR"])


def with_gps_exif(data: bytes) -> bytes:
    image = Image.open(io.BytesIO(data))
    exif = Image.Exif()
    exif[0x010F] = "TestCam"  # Make
    exif[0x8825] = {1: "N", 2: (10.0, 46.0, 36.84), 3: "E", 4: (106.0, 42.0, 3.24)}  # GPS IFD
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def test_cat_photo_creates_sighting():
    response = post_photo(new_user(), fixture("cat_1.jpg"), *fresh_spot())

    assert response.status_code == 201, response.text
    sighting = response.json()["sighting"]
    assert sighting["species"] == "cat"
    assert 0 < sighting["confidence"] <= 1


def test_no_animal_is_rejected_and_nothing_is_stored():
    headers = new_user()
    files_before = set(STORAGE_DIR.iterdir())

    response = post_photo(headers, fixture("none_1.jpg"), *fresh_spot())

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "no_animal"
    assert set(STORAGE_DIR.iterdir()) == files_before
    assert client.get("/sightings/mine", headers=headers).json() == []


def test_my_sightings_lists_only_mine_newest_first():
    me, someone_else = new_user(), new_user()
    first = post_photo(me, fixture("cat_2.jpg"), *fresh_spot()).json()["sighting"]
    second = post_photo(me, fixture("dog_1.jpg"), *fresh_spot()).json()["sighting"]
    post_photo(someone_else, fixture("dog_2.jpg"), *fresh_spot())

    mine = client.get("/sightings/mine", headers=me).json()

    assert [s["id"] for s in mine] == [second["id"], first["id"]]
    assert [s["species"] for s in mine] == ["dog", "cat"]


def test_stored_photo_has_no_exif_and_is_owner_only():
    headers = new_user()
    sighting = post_photo(headers, with_gps_exif(fixture("cat_3.jpg")), *fresh_spot()).json()["sighting"]

    photo = client.get(f"/sightings/{sighting['id']}/photo", headers=headers)
    assert photo.status_code == 200
    assert photo.headers["content-type"] == "image/jpeg"
    assert len(Image.open(io.BytesIO(photo.content)).getexif()) == 0

    stranger = client.get(f"/sightings/{sighting['id']}/photo", headers=new_user())
    assert stranger.status_code == 404


def test_requires_valid_user_id():
    assert client.get("/sightings/mine").status_code == 422
    assert client.get("/sightings/mine", headers={"X-User-Id": "not-a-uuid"}).status_code == 401


def test_rejects_bad_coordinates_and_non_images():
    headers = new_user()
    assert post_photo(headers, fixture("cat_1.jpg"), 91, 0).status_code == 422
    assert post_photo(headers, fixture("cat_1.jpg"), 0, -181).status_code == 422
    assert post_photo(headers, b"definitely not a jpeg", 0, 0).status_code == 415
