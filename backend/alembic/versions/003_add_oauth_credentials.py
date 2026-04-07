"""Add oauth_credentials table for durable provider OAuth tokens.

Revision ID: 003_add_oauth_credentials
Revises: 002_add_llm_configs
Create Date: 2026-04-02 20:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "003_add_oauth_credentials"
down_revision = "002_add_llm_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_credentials",
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("expires_at_ms", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.String(128), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("provider", name="pk_oauth_credentials"),
    )


def downgrade() -> None:
    op.drop_table("oauth_credentials")

