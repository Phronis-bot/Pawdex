"""animal breed

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-26
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Key into app.breeds.BREEDS; null means mixed breed (or not confident).
    op.add_column("animals", sa.Column("breed", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("animals", "breed")
