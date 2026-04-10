"""Add thumbnail_path and igtv_title columns to jobs table.

Revision ID: 005_add_jobs_thumbnail_igtv
Revises: 004_add_llm_config_base_url
Create Date: 2026-04-10 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "005_add_jobs_thumbnail_igtv"
down_revision = "004_add_llm_config_base_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add thumbnail_path and igtv_title to jobs (missing from baseline migration)."""
    op.add_column("jobs", sa.Column("thumbnail_path", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("igtv_title", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove thumbnail_path and igtv_title from jobs."""
    op.drop_column("jobs", "igtv_title")
    op.drop_column("jobs", "thumbnail_path")
