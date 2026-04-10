"""Add templates table for caption template persistence.

Revision ID: 008_add_templates
Revises: 007_add_accounts_health_fields
Create Date: 2026-04-10 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "008_add_templates"
down_revision = "007_accounts_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(128), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_templates"),
    )


def downgrade() -> None:
    op.drop_table("templates")
