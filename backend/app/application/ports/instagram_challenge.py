"""Port for Instagram login challenge resolution.

Instagram occasionally asks the account holder to verify a login by typing a
6-digit code delivered over email or SMS. The vendor SDK blocks in
``challenge_code_handler`` until a code is returned. This port describes the
surface the HTTP layer uses to (a) learn that a challenge is pending and
(b) submit the code entered by the operator so the SDK's login() call can
resume.
"""

from __future__ import annotations

from typing import Protocol

from ..dto.instagram_challenge_dto import (
    ChallengePending,
    ChallengeResolution,
)


class InstagramChallengeResolver(Protocol):
    """Operator-facing surface for resuming an Instagram login challenge."""

    def has_pending(self, account_id: str) -> bool:
        """Return True when a challenge is currently waiting on ``account_id``."""
        ...

    def get_pending(self, account_id: str) -> ChallengePending | None:
        """Return the pending challenge for ``account_id`` or None."""
        ...

    def list_pending(self) -> list[ChallengePending]:
        """Return every challenge currently awaiting operator input."""
        ...

    def submit_code(self, account_id: str, code: str) -> ChallengeResolution:
        """Submit the operator-entered code and let the SDK resume."""
        ...

    def cancel(self, account_id: str) -> ChallengeResolution:
        """Abort the pending challenge so the SDK raises instead of blocking."""
        ...
