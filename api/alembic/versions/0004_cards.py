"""nicknames, coat and rarity

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-25
"""
import sqlalchemy as sa
from alembic import op

from app.nicknames import random_nickname

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("nickname", sa.String(40), nullable=True))
    conn = op.get_bind()
    for (user_id,) in conn.execute(sa.text("SELECT id FROM users")):
        conn.execute(sa.text("UPDATE users SET nickname = :n WHERE id = :id"), {"n": random_nickname(), "id": user_id})
    op.alter_column("users", "nickname", nullable=False)

    # Detected from the discovering photo. Existing animals are filled by
    # `python -m app.backfill_coats`, since that needs the model.
    op.add_column("animals", sa.Column("coat", sa.String(30), nullable=True))
    op.add_column("animals", sa.Column("rarity", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("animals", "rarity")
    op.drop_column("animals", "coat")
    op.drop_column("users", "nickname")
