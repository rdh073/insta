"""Per-account Instagram rate limit cooldown guard.

Tracks which accounts are currently cooling down after a 429 response and
blocks further API calls until the cooldown expires.

Failure-code → cooldown mapping:
  rate_limit       (RateLimitError)         → 3600 s
  wait_required    (PleaseWaitFewMinutes)   → 3600 s
  feedback_required (FeedbackRequired)      → 1800 s

Usage:
    from app.adapters.instagram.rate_limit_guard import rate_limit_guard

    # Before an API call
    limited, retry_after = rate_limit_guard.is_limited(account_id)
    if limited:
        raise InstagramRateLimitError(f"Rate limited for {retry_after:.0f}s")

    # After a 429 failure
    rate_limit_guard.mark_limited(account_id, cooldown_sec=3600, reason="rate_limit")
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)

# Cooldown durations per failure code (seconds)
_COOLDOWNS: dict[str, int] = {
    "rate_limit": 3600,
    "wait_required": 3600,
    "feedback_required": 1800,
}

# Default for any unmapped 429 code
_DEFAULT_COOLDOWN = 3600


@dataclass
class _CooldownEntry:
    limited_until: float  # UNIX timestamp
    reason: str


class AccountRateLimitGuard:
    """Thread-safe per-account cooldown tracker.

    One singleton instance is created at module level and shared across all
    Instagram adapters.  All mutations are protected by a threading.Lock so
    the guard is safe for use from both sync and async contexts.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _CooldownEntry] = {}
        self._lock = Lock()

    # ── Public API ─────────────────────────────────────────────────────────────

    def mark_limited(
        self,
        account_id: str,
        *,
        failure_code: str | None = None,
        cooldown_sec: int | None = None,
        username: str | None = None,
    ) -> None:
        """Mark an account as rate-limited.

        Args:
            account_id: The application account ID.
            failure_code: Failure code from the exception catalog (used to
                          look up the default cooldown duration).
            cooldown_sec: Explicit cooldown override.  If both are provided,
                          ``cooldown_sec`` takes precedence.
            username: Instagram username — if provided, writes a ``rate_limited``
                      entry to the activity audit log.
        """
        duration = (
            cooldown_sec
            if cooldown_sec is not None
            else _COOLDOWNS.get(failure_code or "", _DEFAULT_COOLDOWN)
        )
        reason = failure_code or "rate_limit"
        until = time.monotonic() + duration

        is_new = False
        with self._lock:
            existing = self._entries.get(account_id)
            # Only extend — never shorten an existing cooldown.
            if existing is None or until > existing.limited_until:
                self._entries[account_id] = _CooldownEntry(
                    limited_until=until, reason=reason
                )
                is_new = existing is None

        logger.warning(
            "Account %s rate-limited for %ds (reason=%s)", account_id, duration, reason
        )

        # Write to activity audit log only on first occurrence (not on cooldown extension).
        if is_new and username:
            try:
                from app.adapters.persistence.state_gateway import default_state_gateway
                default_state_gateway.log_event(
                    account_id,
                    username,
                    "rate_limited",
                    detail=f"Cooldown {duration}s ({reason})",
                    status="rate_limited",
                )
            except Exception:
                pass  # Never let audit logging crash the caller

    def is_limited(self, account_id: str) -> tuple[bool, float]:
        """Check whether an account is currently in cooldown.

        Returns:
            (is_limited, retry_after_seconds)
            ``retry_after_seconds`` is 0 when not limited.
        """
        with self._lock:
            entry = self._entries.get(account_id)
            if entry is None:
                return False, 0.0

            remaining = entry.limited_until - time.monotonic()
            if remaining <= 0:
                # Cooldown expired — clean up lazily.
                del self._entries[account_id]
                return False, 0.0

            return True, remaining

    def clear(self, account_id: str) -> None:
        """Manually clear the cooldown for an account (e.g. after re-auth)."""
        with self._lock:
            self._entries.pop(account_id, None)

    def get_all_limited(self) -> dict[str, dict]:
        """Return a snapshot of all currently rate-limited accounts.

        Returns:
            Dict keyed by account_id with ``{"retry_after": float, "reason": str}``.
        """
        now = time.monotonic()
        result: dict[str, dict] = {}
        with self._lock:
            expired = [
                aid for aid, e in self._entries.items() if e.limited_until <= now
            ]
            for aid in expired:
                del self._entries[aid]
            for aid, entry in self._entries.items():
                result[aid] = {
                    "retry_after": entry.limited_until - now,
                    "reason": entry.reason,
                }
        return result


# Module-level singleton shared by all Instagram adapters.
rate_limit_guard = AccountRateLimitGuard()
