"""animals and sighting embeddings

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "animals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("species", postgresql.ENUM(name="species", create_type=False), nullable=False),
        sa.Column("name", sa.String(30), nullable=True),
        sa.Column("discoverer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("sightings", sa.Column("animal_id", sa.Uuid(), sa.ForeignKey("animals.id"), nullable=True))
    # No fixed dimension: candidates are pre-filtered by radius, so no ANN index is needed,
    # and embedding_model keeps vectors from different models from being compared.
    op.add_column("sightings", sa.Column("embedding", Vector(), nullable=True))
    op.add_column("sightings", sa.Column("embedding_model", sa.String(40), nullable=True))
    op.create_index("ix_sightings_animal_id", "sightings", ["animal_id"])


def downgrade() -> None:
    op.drop_index("ix_sightings_animal_id", table_name="sightings")
    op.drop_column("sightings", "embedding_model")
    op.drop_column("sightings", "embedding")
    op.drop_column("sightings", "animal_id")
    op.drop_table("animals")
