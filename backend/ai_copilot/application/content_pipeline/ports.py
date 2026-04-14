"""Ports for Content Pipeline workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Final, TypedDict


ALLOWED_SCHEDULE_RESULT_STATUSES: Final[frozenset[str]] = frozenset({
    "scheduled",
    "queued",
    "pending",
})


class ScheduledPostResult(TypedDict, total=False):
    """Expected scheduler payload for Content Pipeline success checks."""

    job_id: str
    status: str
    scheduled_at: str | None


class CaptionGeneratorPort(ABC):
    @abstractmethod
    async def generate(
        self,
        campaign_brief: str,
        media_refs: list[str],
        previous_feedback: str | None = None,
        attempt: int = 1,
    ) -> str:
        """Generate a caption for the given brief and media. Returns caption string."""


class CaptionValidatorPort(ABC):
    @abstractmethod
    async def validate(self, caption: str, campaign_brief: str) -> dict:
        """Validate caption. Returns {passed: bool, errors: list[str], feedback: str}."""


class PostSchedulerPort(ABC):
    @abstractmethod
    async def schedule(
        self,
        usernames: list[str],
        caption: str,
        media_refs: list[str],
        scheduled_at: str | None = None,
    ) -> ScheduledPostResult:
        """Schedule a post job.

        Returns:
            Dict with at least:
            - job_id: non-empty identifier
            - status: one of ALLOWED_SCHEDULE_RESULT_STATUSES
            - scheduled_at: optional schedule timestamp
        """
