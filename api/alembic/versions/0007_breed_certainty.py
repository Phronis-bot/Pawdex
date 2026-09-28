"""breed certainty

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # "confirmed" or "likely"; null together with breed. Breeds stored so far were all confirmed.
    op.add_column("animals", sa.Column("breed_certainty", sa.String(10), nullable=True))
    op.execute("UPDATE animals SET breed_certainty = 'confirmed' WHERE breed IS NOT NULL")


def downgrade() -> None:
    op.drop_column("animals", "breed_certainty")
