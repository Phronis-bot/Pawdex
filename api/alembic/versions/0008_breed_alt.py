"""breed second guess

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Second guess of a "maybe" breed ("Maybe a Birman or a Himalayan").
    op.add_column("animals", sa.Column("breed_alt", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("animals", "breed_alt")
