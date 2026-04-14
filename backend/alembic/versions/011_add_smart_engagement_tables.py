"""Add smart engagement approval and audit persistence tables.

Revision ID: 011_add_smart_engagement_tables
Revises: 010_merge_009_accounts_heads
Create Date: 2026-04-14 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "011_add_smart_engagement_tables"
down_revision = "010_merge_009_accounts_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "smart_engagement_approvals",
        sa.Column("approval_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_at", sa.Float(), nullable=False),
        sa.Column("approved_at", sa.Float(), nullable=True),
        sa.Column("approver_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("action_id", sa.Text(), nullable=False),
        sa.Column("action_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("risk_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("audit_payload", sa.JSON(), nullable=False, server_default="[]"),
        sa.PrimaryKeyConstraint("approval_id", name="pk_smart_engagement_approvals"),
    )
    op.create_index(
        "ix_se_approvals_status",
        "smart_engagement_approvals",
        ["status"],
        unique=False,
    )

    op.create_table(
        "smart_engagement_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("node_name", sa.String(length=128), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_smart_engagement_audit_events"),
    )
    op.create_index(
        "ix_se_audit_thread_id",
        "smart_engagement_audit_events",
        ["thread_id"],
        unique=False,
    )
    op.create_index(
        "ix_se_audit_timestamp",
        "smart_engagement_audit_events",
        ["timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_se_audit_timestamp", table_name="smart_engagement_audit_events")
    op.drop_index("ix_se_audit_thread_id", table_name="smart_engagement_audit_events")
    op.drop_table("smart_engagement_audit_events")

    op.drop_index("ix_se_approvals_status", table_name="smart_engagement_approvals")
    op.drop_table("smart_engagement_approvals")
