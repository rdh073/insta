"""Ports for Content Pipeline workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod


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
    ) -> dict:
        """Schedule a post job. Returns {job_id, status, scheduled_at}."""
