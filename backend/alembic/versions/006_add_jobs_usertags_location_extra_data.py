"""Add usertags, location, and extra_data columns to jobs table.

Revision ID: 006_add_jobs_usertags_location_extra_data
Revises: 005_add_jobs_thumbnail_igtv
Create Date: 2026-04-10 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "006_jobs_extra_fields"
down_revision = "005_add_jobs_thumbnail_igtv"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add usertags, location, extra_data to jobs table.

    These fields exist in JobRecord but were never persisted to SQL,
    causing silent data loss when PERSISTENCE_BACKEND=sqlite or sql.
    """
    op.add_column(
        "jobs",
        sa.Column("usertags", sa.JSON(), nullable=True, server_default="[]"),
    )
    op.add_column(
        "jobs",
        sa.Column("location", sa.JSON(), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("extra_data", sa.JSON(), nullable=True, server_default="{}"),
    )


def downgrade() -> None:
    """Remove usertags, location, extra_data from jobs."""
    op.drop_column("jobs", "extra_data")
    op.drop_column("jobs", "location")
    op.drop_column("jobs", "usertags")
