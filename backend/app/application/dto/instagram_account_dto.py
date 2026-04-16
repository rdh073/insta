"""
Instagram account DTO for write/edit operations.

Captures the subset of authenticated-account fields that are mutated by
account_writer (privacy, profile edit, avatar, presence). Returned by every
InstagramAccountWriter mutation so callers receive the post-mutation snapshot
without needing a follow-up read.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AccountProfile:
    """Authenticated-account snapshot returned after a write mutation."""

    id: int
    """Instagram account primary key (pk)."""

    username: str
    """Account username."""

    is_private: Optional[bool] = None
    """Whether the account is private."""

    full_name: Optional[str] = None
    """Display name."""

    biography: Optional[str] = None
    """Profile bio text."""

    external_url: Optional[str] = None
    """External URL in profile (link in bio)."""

    profile_pic_url: Optional[str] = None
    """URL to profile picture."""

    presence_disabled: Optional[bool] = None
    """Whether 'last active' presence is hidden from other users."""
