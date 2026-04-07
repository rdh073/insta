"""Engagement candidate adapter - thin adapter over app-owned data seams."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ai_copilot.application.smart_engagement.ports import EngagementCandidatePort
from ai_copilot.application.smart_engagement.state import EngagementTarget


@runtime_checkable
class CandidateDataPort(Protocol):
    async def get_followers(
        self,
        account_id: str,
        limit: int = 100,
        filters: dict | None = None,
    ) -> list[EngagementTarget]:
        pass

    async def get_following(
        self,
        account_id: str,
        limit: int = 100,
        filters: dict | None = None,
    ) -> list[EngagementTarget]:
        pass

    async def get_recent_posts(
        self,
        account_id: str,
        limit: int = 50,
        filters: dict | None = None,
    ) -> list[EngagementTarget]:
        pass

    async def get_target_metadata(self, account_id: str, target_id: str) -> dict:
        pass


class EngagementCandidateAdapter(EngagementCandidatePort):
    """Discovers candidates by delegating to instagram data adapter seams."""

    def __init__(self, data_port: CandidateDataPort):
        self.data_port = data_port

    async def discover_candidates(
        self,
        account_id: str,
        goal: str,
        filters: dict | None = None,
    ) -> list[EngagementTarget]:
        normalized_filters = dict(filters or {})
        max_results = int(normalized_filters.pop("max_results", 5))
        if max_results <= 0:
            return []

        source = self._resolve_source(goal)
        if source == "followers":
            candidates = await self.data_port.get_followers(
                account_id=account_id,
                limit=max_results,
                filters=normalized_filters,
            )
        elif source == "following":
            candidates = await self.data_port.get_following(
                account_id=account_id,
                limit=max_results,
                filters=normalized_filters,
            )
        else:
            candidates = await self.data_port.get_recent_posts(
                account_id=account_id,
                limit=max_results,
                filters=normalized_filters,
            )
        return candidates[:max_results]

    async def get_target_metadata(self, target_id: str) -> dict:
        # Interface kept for backward compatibility; use explicit account-aware helper.
        return {"target_id": target_id}

    async def get_target_metadata_for_account(self, account_id: str, target_id: str) -> dict:
        """Account-aware metadata lookup for ai_copilot internals."""
        return await self.data_port.get_target_metadata(account_id=account_id, target_id=target_id)

    def _resolve_source(self, goal: str) -> str:
        text = (goal or "").lower()
        if "followers" in text or "follower" in text:
            return "followers"
        if "following" in text:
            return "following"
        if "post" in text or "comment" in text or "reel" in text:
            return "posts"
        return "followers"
