"""coat picked by the player, country of discovery

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("animals", sa.Column("coat_by_player", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("animals", sa.Column("country", sa.String(2), nullable=True))


def downgrade() -> None:
    op.drop_column("animals", "country")
    op.drop_column("animals", "coat_by_player")
