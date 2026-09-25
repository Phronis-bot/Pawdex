"""Tests run against a separate `<dev db>_test` database with migrations applied."""
import os
import tempfile

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
