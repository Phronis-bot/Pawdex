"""users and sightings

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25
"""
import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "sightings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("species", sa.Enum("cat", "dog", name="species"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("photo_key", sa.String(255), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.Geography("POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # GiST index for the "animals within N metres" queries of phase 2.
    op.create_index("ix_sightings_location", "sightings", ["location"], postgresql_using="gist")
    op.create_index("ix_sightings_user_id", "sightings", ["user_id"])
    op.create_index("ix_sightings_created_at", "sightings", ["created_at"])


def downgrade() -> None:
    op.drop_table("sightings")
    op.drop_table("users")
    sa.Enum(name="species").drop(op.get_bind(), checkfirst=True)
