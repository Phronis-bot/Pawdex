"""photo reports

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sightings", sa.Column("hidden", sa.Boolean(), server_default="false", nullable=False))
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sighting_id", sa.Uuid(), sa.ForeignKey("sightings.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("sighting_id", "user_id"),
    )
    op.create_index("ix_reports_sighting_id", "reports", ["sighting_id"])


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_column("sightings", "hidden")
