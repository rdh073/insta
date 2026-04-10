"""Add account health tracking fields to accounts table.

Revision ID: 007_add_accounts_health_fields
Revises: 006_add_jobs_usertags_location_extra_data
Create Date: 2026-04-10 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "007_add_accounts_health_fields"
down_revision = "006_add_jobs_usertags_location_extra_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add profile_pic_url, last_verified_at, last_error, last_error_code to accounts.

    These fields exist in AccountRecord for session health tracking but were
    never persisted to SQL, causing connectivity diagnostics to be lost on restart.
    """
    op.add_column(
        "accounts",
        sa.Column("profile_pic_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("last_verified_at", sa.String(128), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("last_error_code", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    """Remove account health tracking fields."""
    op.drop_column("accounts", "last_error_code")
    op.drop_column("accounts", "last_error")
    op.drop_column("accounts", "last_verified_at")
    op.drop_column("accounts", "profile_pic_url")
