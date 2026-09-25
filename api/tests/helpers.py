import random
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"

client = TestClient(app)

# ~111 m and ~1.1 km of latitude.
NEARBY = 0.001
FAR = 0.01


def new_user() -> dict[str, str]:
    return {"X-User-Id": str(uuid.uuid4())}


def fresh_spot() -> tuple[float, float]:
    """A random place around Ho Chi Minh City, far (tens of km) from other tests' animals."""
    return 10.5 + random.random() * 0.5, 106.5 + random.random() * 0.5


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def post_photo(headers, data: bytes, lat: float, lon: float):
    return client.post(
        "/sightings",
        headers=headers,
        files={"photo": ("photo.jpg", data, "image/jpeg")},
        data={"latitude": str(lat), "longitude": str(lon)},
    )
