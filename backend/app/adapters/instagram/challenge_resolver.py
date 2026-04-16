"""Process-local Instagram challenge resolver.

Bridges instagrapi's synchronous ``challenge_code_handler`` hook to the
operator via HTTP. When the SDK asks for a 6-digit code during ``login()``,
the hook:

1. Publishes a :class:`ChallengePending` entry keyed by ``account_id`` so the
   HTTP layer can display it.
2. Blocks on a :class:`threading.Event` until the operator posts the code
   (``submit_code``), cancels (``cancel``), or the wait times out.
3. Returns the submitted code so instagrapi's internal flow continues.

Residual risk — kept intentionally simple for this iteration:

- State lives only in the current Python process. A restart drops pending
  challenges; the operator must re-trigger the login.
- There is no multi-process coordination. The ``has_pending``/``submit_code``
  call must hit the same worker that owns the waiting SDK thread.

See :class:`~app.application.ports.instagram_challenge.InstagramChallengeResolver`
for the operator-facing contract and ``backend/.env.example`` for
``CHALLENGE_WAIT_TIMEOUT_SECONDS``.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from app.application.dto.instagram_challenge_dto import (
    ChallengeMethod,
    ChallengePending,
    ChallengeResolution,
)


logger = logging.getLogger(__name__)

DEFAULT_CHALLENGE_WAIT_TIMEOUT_SECONDS = 600
CHALLENGE_WAIT_TIMEOUT_ENV = "CHALLENGE_WAIT_TIMEOUT_SECONDS"


def _resolve_default_timeout() -> float:
    raw = os.getenv(CHALLENGE_WAIT_TIMEOUT_ENV)
    if raw is None or not raw.strip():
        return float(DEFAULT_CHALLENGE_WAIT_TIMEOUT_SECONDS)
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "challenge_resolver: invalid %s=%r, falling back to default %ss",
            CHALLENGE_WAIT_TIMEOUT_ENV,
            raw,
            DEFAULT_CHALLENGE_WAIT_TIMEOUT_SECONDS,
        )
        return float(DEFAULT_CHALLENGE_WAIT_TIMEOUT_SECONDS)
    if value <= 0:
        logger.warning(
            "challenge_resolver: non-positive %s=%r, using default",
            CHALLENGE_WAIT_TIMEOUT_ENV,
            raw,
        )
        return float(DEFAULT_CHALLENGE_WAIT_TIMEOUT_SECONDS)
    return value


def _method_from_choice(choice: object) -> ChallengeMethod:
    """Normalize instagrapi's ``choice`` hint into a stable enum value.

    instagrapi hands the hook either an enum-like object (``choice.name``) or
    an integer/str. ``0`` / ``SMS`` means SMS, ``1`` / ``EMAIL`` means email.
    """
    name = getattr(choice, "name", None)
    if isinstance(name, str):
        upper = name.upper()
        if upper in {"EMAIL", "SMS"}:
            return upper  # type: ignore[return-value]
    if isinstance(choice, str):
        upper = choice.upper()
        if upper in {"EMAIL", "SMS"}:
            return upper  # type: ignore[return-value]
    if isinstance(choice, int):
        if choice == 0:
            return "SMS"
        if choice == 1:
            return "EMAIL"
    return "UNKNOWN"


@dataclass
class _PendingEntry:
    pending: ChallengePending
    event: threading.Event
    code: Optional[str] = None
    cancelled: bool = False


class InstagramChallengeResolverAdapter:
    """In-process adapter implementing :class:`InstagramChallengeResolver`."""

    def __init__(
        self,
        *,
        default_timeout_seconds: float | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._default_timeout = (
            float(default_timeout_seconds)
            if default_timeout_seconds is not None
            else _resolve_default_timeout()
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._pending: dict[str, _PendingEntry] = {}
        self._username_to_account: dict[str, str] = {}

    # ── Operator-facing surface ───────────────────────────────────────────
    def has_pending(self, account_id: str) -> bool:
        with self._lock:
            return account_id in self._pending

    def get_pending(self, account_id: str) -> ChallengePending | None:
        with self._lock:
            entry = self._pending.get(account_id)
            return entry.pending if entry else None

    def list_pending(self) -> list[ChallengePending]:
        with self._lock:
            return [entry.pending for entry in self._pending.values()]

    def submit_code(self, account_id: str, code: str) -> ChallengeResolution:
        normalized = (code or "").strip()
        if not normalized:
            return ChallengeResolution(
                account_id=account_id,
                status="failed",
                message="Challenge code cannot be empty.",
                next_step="manual",
            )
        with self._lock:
            entry = self._pending.get(account_id)
            if entry is None:
                return ChallengeResolution(
                    account_id=account_id,
                    status="failed",
                    message="No pending challenge for this account.",
                    next_step="manual",
                )
            entry.code = normalized
            entry.cancelled = False
            entry.event.set()
        logger.info(
            "challenge_resolver.submit: account_id=%s code_len=%d",
            account_id,
            len(normalized),
        )
        return ChallengeResolution(
            account_id=account_id,
            status="resolved",
            message="Challenge code submitted.",
            next_step="relogin",
        )

    def cancel(self, account_id: str) -> ChallengeResolution:
        with self._lock:
            entry = self._pending.get(account_id)
            if entry is None:
                return ChallengeResolution(
                    account_id=account_id,
                    status="failed",
                    message="No pending challenge for this account.",
                    next_step="manual",
                )
            entry.cancelled = True
            entry.code = None
            entry.event.set()
        logger.info("challenge_resolver.cancel: account_id=%s", account_id)
        return ChallengeResolution(
            account_id=account_id,
            status="cancelled",
            message="Challenge cancelled by operator.",
            next_step="manual",
        )

    # ── Runtime plumbing seated into instagrapi ─────────────────────────
    def register_account(self, account_id: str, username: str) -> None:
        """Associate a username with an account_id so the SDK hook can route back.

        The SDK hook only knows the Instagram username. AuthUseCases calls
        this before login() so the hook resolves ``account_id`` correctly.
        """
        if not account_id or not username:
            return
        with self._lock:
            self._username_to_account[username.lower()] = account_id

    def unregister_account(self, username: str) -> None:
        if not username:
            return
        with self._lock:
            self._username_to_account.pop(username.lower(), None)

    def _resolve_account_id(self, username: str) -> str:
        """Return the account_id bound to ``username``; fall back to the username."""
        with self._lock:
            return self._username_to_account.get(
                (username or "").lower(),
                username or "unknown",
            )

    def handle_challenge_code_request(
        self,
        username: str,
        choice: object,
        *,
        timeout_seconds: float | None = None,
    ) -> str:
        """Callable seated into instagrapi's ``challenge_code_handler``.

        Blocks until ``submit_code`` or ``cancel`` is called, or the
        configured timeout expires. Returns the 6-digit code on success.

        Raises:
            ChallengeCancelledError: Operator cancelled the challenge.
            ChallengeTimeoutError: Timed out waiting for operator input.
        """
        account_id = self._resolve_account_id(username)
        method = _method_from_choice(choice)
        contact_hint = getattr(choice, "value", None)
        if not isinstance(contact_hint, str):
            contact_hint = None
        pending = ChallengePending(
            account_id=account_id,
            username=username or "",
            method=method,
            contact_hint=contact_hint,
            created_at=self._clock().isoformat(),
        )
        event = threading.Event()
        entry = _PendingEntry(pending=pending, event=event)
        with self._lock:
            # If a stale entry exists (orphan), replace it so the new login
            # attempt is not wedged behind a dead one.
            self._pending[account_id] = entry

        wait_for = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else self._default_timeout
        )
        logger.info(
            "challenge_resolver.wait: account_id=%s username=%s method=%s timeout=%.1fs",
            account_id,
            username,
            method,
            wait_for,
        )
        signalled = event.wait(timeout=wait_for)

        with self._lock:
            current = self._pending.get(account_id)
            # Only remove the entry we created — a newer attempt might have
            # replaced it concurrently; leave that one untouched.
            if current is entry:
                self._pending.pop(account_id, None)
            cancelled = entry.cancelled
            code = entry.code

        if not signalled:
            raise ChallengeTimeoutError(
                f"Timed out waiting for operator challenge code for @{username}."
            )
        if cancelled or code is None:
            raise ChallengeCancelledError(
                f"Operator cancelled challenge for @{username}."
            )
        return code


class ChallengeTimeoutError(RuntimeError):
    """Raised when the operator does not submit a code within the timeout."""


class ChallengeCancelledError(RuntimeError):
    """Raised when the operator explicitly cancels a pending challenge."""


# Sentinel singleton used by `instagram_runtime.auth` when the bootstrap has
# not seated a concrete resolver yet (e.g. during tests that import auth
# directly without going through the container).
_CURRENT_RESOLVER: InstagramChallengeResolverAdapter | None = None


def set_current_resolver(resolver: InstagramChallengeResolverAdapter | None) -> None:
    global _CURRENT_RESOLVER
    _CURRENT_RESOLVER = resolver


def get_current_resolver() -> InstagramChallengeResolverAdapter | None:
    return _CURRENT_RESOLVER
