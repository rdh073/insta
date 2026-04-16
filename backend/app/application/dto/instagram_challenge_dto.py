"""DTOs for Instagram login challenge resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


ChallengeMethod = Literal["EMAIL", "SMS", "UNKNOWN"]
ChallengeResolutionStatus = Literal["resolved", "failed", "expired", "cancelled"]
ChallengeNextStep = Literal["ok", "relogin", "manual"]


@dataclass(frozen=True)
class ChallengePending:
    """Surface for an in-flight Instagram challenge awaiting operator input."""

    account_id: str
    username: str
    method: ChallengeMethod
    contact_hint: Optional[str]
    created_at: str


@dataclass(frozen=True)
class ChallengeResolution:
    """Outcome of a submit_code() / cancel() call on a pending challenge."""

    account_id: str
    status: ChallengeResolutionStatus
    message: str
    next_step: ChallengeNextStep
