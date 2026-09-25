import io
import os
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"
STORAGE_DIR = Path(os.environ["PAWDEX_STORAGE_DIR"])

client = TestClient(app)

# Somewhere in District 1, Ho Chi Minh City.
LAT, LON = 10.7769, 106.7009


def new_user() -> dict[str, str]:
    return {"X-User-Id": str(uuid.uuid4())}


def post_photo(headers, data: bytes, lat=LAT, lon=LON):
    return client.post(
        "/sightings",
        headers=headers,
        files={"photo": ("photo.jpg", data, "image/jpeg")},
        data={"latitude": str(lat), "longitude": str(lon)},
    )


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def with_gps_exif(data: bytes) -> bytes:
    image = Image.open(io.BytesIO(data))
    exif = Image.Exif()
    exif[0x010F] = "TestCam"  # Make
    exif[0x8825] = {1: "N", 2: (10.0, 46.0, 36.84), 3: "E", 4: (106.0, 42.0, 3.24)}  # GPS IFD
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def test_cat_photo_creates_sighting():
    headers = new_user()
    response = post_photo(headers, fixture("cat_1.jpg"))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["species"] == "cat"
    assert 0 < body["confidence"] <= 1


def test_no_animal_is_rejected_and_nothing_is_stored():
    headers = new_user()
    files_before = set(STORAGE_DIR.iterdir())

    response = post_photo(headers, fixture("none_1.jpg"))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "no_animal"
    assert set(STORAGE_DIR.iterdir()) == files_before
    assert client.get("/sightings/mine", headers=headers).json() == []


def test_my_sightings_lists_only_mine_newest_first():
    me, someone_else = new_user(), new_user()
    first = post_photo(me, fixture("cat_2.jpg")).json()
    second = post_photo(me, fixture("dog_1.jpg")).json()
    post_photo(someone_else, fixture("dog_2.jpg"))

    mine = client.get("/sightings/mine", headers=me).json()

    assert [s["id"] for s in mine] == [second["id"], first["id"]]
    assert [s["species"] for s in mine] == ["dog", "cat"]


def test_responses_never_contain_coordinates():
    headers = new_user()
    created = post_photo(headers, fixture("dog_3.jpg"))
    listed = client.get("/sightings/mine", headers=headers)

    for text in (created.text, listed.text):
        assert str(LAT) not in text and str(LON) not in text
        for field in ("lat", "lon", "latitude", "longitude", "location"):
            assert f'"{field}"' not in text


def test_stored_photo_has_no_exif_and_is_owner_only():
    headers = new_user()
    sighting = post_photo(headers, with_gps_exif(fixture("cat_3.jpg"))).json()

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
    assert post_photo(headers, fixture("cat_1.jpg"), lat=91).status_code == 422
    assert post_photo(headers, fixture("cat_1.jpg"), lon=-181).status_code == 422
    assert post_photo(headers, b"definitely not a jpeg").status_code == 415
