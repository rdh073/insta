"""Add llm_configs table for LLM provider configuration.

Revision ID: 002_add_llm_configs
Revises: 001_baseline_schema
Create Date: 2026-04-02 12:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = "002_add_llm_configs"
down_revision = "001_baseline_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create llm_configs table with encrypted api_key storage."""
    op.create_table(
        "llm_configs",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_llm_configs"),
    )

    # Partial unique index: at most one active config at a time.
    # Note: PostgreSQL supports WHERE clause in partial indices.
    # SQLite ignores WHERE but still enforces uniqueness on the boolean column.
    # For SQLite compatibility we skip the partial index and rely on app-level enforcement.
    # For PostgreSQL, uncomment the line below after ensuring PostgreSQL dialect:
    # op.create_index("uix_llm_configs_one_active", "llm_configs", ["is_active"], unique=True, postgresql_where=sa.text("is_active = TRUE"))


def downgrade() -> None:
    """Drop llm_configs table."""
    op.drop_table("llm_configs")
