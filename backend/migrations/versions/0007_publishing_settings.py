"""Add singleton publishing automation settings."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publishing_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("posts_per_day", sa.Integer(), server_default="1", nullable=False),
        sa.Column("automation_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="Africa/Addis_Ababa", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("publishing_settings")
