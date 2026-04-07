"""Add base_url column to llm_configs table.

Revision ID: 004_add_llm_config_base_url
Revises: 003_add_oauth_credentials
Create Date: 2026-04-06 12:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "004_add_llm_config_base_url"
down_revision = "003_add_oauth_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable base_url column to llm_configs."""
    op.add_column(
        "llm_configs",
        sa.Column("base_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove base_url column from llm_configs."""
    op.drop_column("llm_configs", "base_url")
