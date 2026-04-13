"""Merge parallel 009 account schema heads.

Revision ID: 010_merge_009_accounts_heads
Revises: 009_accounts_geo_locale, 009_accounts_last_error_family
Create Date: 2026-04-12 00:00:00.000000
"""

from __future__ import annotations


revision = "010_merge_009_accounts_heads"
down_revision = ("009_accounts_geo_locale", "009_accounts_last_error_family")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge migration graph only; no schema changes."""


def downgrade() -> None:
    """Split migration graph only; no schema changes."""
