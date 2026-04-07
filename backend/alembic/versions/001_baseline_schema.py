"""Baseline schema for account, job, and status persistence.

Revision ID: 001_baseline_schema
Revises:
Create Date: 2026-04-02 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001_baseline_schema"
down_revision = None
branch_labels = None
depends_on = None

# Naming conventions for consistency
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def upgrade() -> None:
    """Create baseline persistence tables for accounts, account status, and jobs."""
    # Create accounts table
    op.create_table(
        "accounts",
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("username", sa.String(255), nullable=False, index=True, unique=True),
        sa.Column("password", sa.Text(), nullable=False, server_default=""),
        sa.Column("proxy", sa.Text(), nullable=True),
        sa.Column("totp_secret", sa.Text(), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("followers", sa.Integer(), nullable=True),
        sa.Column("following", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("account_id", name="pk_accounts"),
    )

    # Create account_status table
    op.create_table(
        "account_status",
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("account_id", name="pk_account_status"),
    )

    # Create jobs table for post scheduling and execution
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(64), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(128), nullable=False, server_default=""),
        sa.Column("media_type", sa.String(64), nullable=False, server_default="photo"),
        sa.Column("scheduled_at", sa.String(128), nullable=True),
        sa.Column("targets", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("results", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("media_urls", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("media_paths", sa.JSON(), nullable=False, server_default="[]"),
        sa.PrimaryKeyConstraint("job_id", name="pk_jobs"),
    )


def downgrade() -> None:
    """Drop all persistence tables."""
    op.drop_table("jobs")
    op.drop_table("account_status")
    op.drop_table("accounts")
