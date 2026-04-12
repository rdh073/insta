"""Domain entities for account management."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AccountStatus(str, Enum):
    """Account lifecycle states."""
    ACTIVE = "active"
    IDLE = "idle"
    ERROR = "error"
    TWO_FA_REQUIRED = "2fa_required"
    REMOVED = "removed"


@dataclass
class Account:
    """Core account entity with invariants."""

    id: str
    username: str
    status: AccountStatus = AccountStatus.IDLE
    password: Optional[str] = None
    proxy: Optional[str] = None
    full_name: Optional[str] = None
    followers: Optional[int] = None
    following: Optional[int] = None
    totp_secret: Optional[str] = None
    # Session health tracking
    last_verified_at: Optional[str] = None  # ISO timestamp of last successful Instagram interaction
    last_error: Optional[str] = None
    last_error_code: Optional[str] = None
    last_error_family: Optional[str] = None

    # Invariants
    def validate(self) -> None:
        """Validate account invariants."""
        if not self.id:
            raise ValueError("Account must have an ID")
        if not self.username:
            raise ValueError("Account must have a username")

        # Active accounts must have valid state
        if self.status == AccountStatus.ACTIVE:
            # Active accounts should have been authenticated (no validation needed for in-memory)
            pass

    def is_logged_in(self) -> bool:
        """Check if account is in a logged-in state."""
        return self.status == AccountStatus.ACTIVE

    def is_idle(self) -> bool:
        """Check if account has no active session."""
        return self.status == AccountStatus.IDLE
