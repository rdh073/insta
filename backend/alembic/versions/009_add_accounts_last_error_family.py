"""Add last_error_family to accounts table.

Revision ID: 009_accounts_last_error_family
Revises: 008_add_templates
Create Date: 2026-04-12 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "009_accounts_last_error_family"
down_revision = "008_add_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add last_error_family session health field to accounts."""
    op.add_column(
        "accounts",
        sa.Column("last_error_family", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    """Remove last_error_family session health field from accounts."""
    op.drop_column("accounts", "last_error_family")
