"""Tests run against a separate `<dev db>_test` database with migrations applied."""
import math
import os
import random
import tempfile

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

_dev_url = make_url(os.environ.get("PAWDEX_DATABASE_URL", "postgresql+psycopg://pawdex:pawdex@localhost:5432/pawdex"))
_test_url = _dev_url.set(database=f"{_dev_url.database}_test")

# Must happen before anything imports app.config.
os.environ["PAWDEX_DATABASE_URL"] = _test_url.render_as_string(hide_password=False)
os.environ["PAWDEX_STORAGE_DIR"] = tempfile.mkdtemp(prefix="pawdex-photos-")


def _prepare_database() -> None:
    admin = create_engine(_dev_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{_test_url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{_test_url.database}"'))
    admin.dispose()

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini")), "head")


def pytest_configure(config):
    _prepare_database()


DIM = 64


class FakeEmbedder:
    """Returns queued vectors so tests control similarity; random (unrelated) ones otherwise."""

    name = "fake"

    def __init__(self):
        self.queue: list[list[float]] = []

    def embed(self, image):
        if self.queue:
            return self.queue.pop(0)
        v = [random.gauss(0, 1) for _ in range(DIM)]
        norm = math.sqrt(sum(x * x for x in v))
        return [x / norm for x in v]


def vector_with_similarity(similarity: float) -> list[float]:
    """A unit vector whose cosine similarity to BASE_VECTOR is exactly `similarity`."""
    return [similarity, math.sqrt(1 - similarity**2)] + [0.0] * (DIM - 2)


BASE_VECTOR = vector_with_similarity(1.0)


@pytest.fixture
def fake_embedder():
    from app.embedder import get_embedder
    from app.main import app

    fake = FakeEmbedder()
    app.dependency_overrides[get_embedder] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_embedder, None)
