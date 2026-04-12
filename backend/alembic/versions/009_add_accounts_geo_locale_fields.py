"""Add geo-locale fields to accounts table.

Revision ID: 009_accounts_geo_locale
Revises: 008_add_templates
Create Date: 2026-04-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "009_accounts_geo_locale"
down_revision = "008_add_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add optional account geo-locale configuration columns."""
    op.add_column(
        "accounts",
        sa.Column("country", sa.String(2), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("country_code", sa.Integer(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("locale", sa.String(32), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("timezone_offset", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove account geo-locale configuration columns."""
    op.drop_column("accounts", "timezone_offset")
    op.drop_column("accounts", "locale")
    op.drop_column("accounts", "country_code")
    op.drop_column("accounts", "country")
