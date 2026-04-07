"""Engagement memory adapter — implements EngagementMemoryPort using LangGraph Store.

Infrastructure concern: wraps LangGraph's BaseStore to provide cross-thread
engagement memory. Nodes access this through the port interface, not the Store
directly.

Namespace layout:
    (account_id, "engagements")  → past engagement outcomes
    (account_id, "rejections")   → operator-rejected targets (subset)

The same Store instance is passed to graph.compile(store=store) AND to this
adapter. The adapter uses it synchronously via store.put/store.search; the
graph uses it for its own checkpointing purposes.
"""

from __future__ import annotations

import logging
import time
import uuid

from ai_copilot.application.smart_engagement.ports import EngagementMemoryPort
from ai_copilot.application.smart_engagement.state import EngagementMemoryRecord

logger = logging.getLogger(__name__)


class LangGraphStoreMemoryAdapter(EngagementMemoryPort):
    """Cross-thread engagement memory backed by a LangGraph Store."""

    def __init__(self, store):
        """Initialize with a LangGraph BaseStore instance.

        Args:
            store: Any LangGraph store (InMemoryStore, PostgresStore, etc.)
        """
        self._store = store

    async def recall_recent_engagements(
        self,
        account_id: str,
        limit: int = 20,
    ) -> list[EngagementMemoryRecord]:
        namespace = (account_id, "engagements")
        try:
            items = await self._store.asearch(namespace, limit=limit)
            records = []
            for item in items:
                val = item.value
                records.append(EngagementMemoryRecord(
                    target_id=val.get("target_id", ""),
                    action_type=val.get("action_type", ""),
                    outcome=val.get("outcome", ""),
                    account_id=val.get("account_id", account_id),
                    timestamp=val.get("timestamp", 0.0),
                ))
            records.sort(key=lambda r: r["timestamp"], reverse=True)
            return records[:limit]
        except Exception:
            logger.exception("Failed to recall engagements for account=%s", account_id)
            return []

    async def store_engagement_outcome(
        self,
        account_id: str,
        target_id: str,
        action_type: str,
        outcome: str,
    ) -> None:
        namespace = (account_id, "engagements")
        record_id = str(uuid.uuid4())
        value = {
            "target_id": target_id,
            "action_type": action_type,
            "outcome": outcome,
            "account_id": account_id,
            "timestamp": time.time(),
        }
        try:
            await self._store.aput(namespace, record_id, value)
            logger.debug(
                "Stored engagement outcome account=%s target=%s outcome=%s",
                account_id, target_id, outcome,
            )
        except Exception:
            logger.exception(
                "Failed to store engagement outcome account=%s target=%s",
                account_id, target_id,
            )

        # Also index rejections separately for fast lookup
        if outcome == "rejected":
            rej_namespace = (account_id, "rejections")
            try:
                await self._store.aput(rej_namespace, target_id, {
                    "target_id": target_id,
                    "rejected_at": time.time(),
                })
            except Exception:
                logger.exception(
                    "Failed to store rejection record account=%s target=%s",
                    account_id, target_id,
                )

    async def recall_rejected_targets(
        self,
        account_id: str,
        limit: int = 50,
    ) -> set[str]:
        namespace = (account_id, "rejections")
        try:
            items = await self._store.asearch(namespace, limit=limit)
            return {item.value.get("target_id", "") for item in items} - {""}
        except Exception:
            logger.exception("Failed to recall rejections for account=%s", account_id)
            return set()


class InMemoryEngagementMemoryAdapter(EngagementMemoryPort):
    """Simple in-memory implementation for testing (no LangGraph dependency)."""

    def __init__(self):
        self._engagements: dict[str, list[dict]] = {}
        self._rejections: dict[str, set[str]] = {}

    async def recall_recent_engagements(
        self,
        account_id: str,
        limit: int = 20,
    ) -> list[EngagementMemoryRecord]:
        records = self._engagements.get(account_id, [])
        sorted_records = sorted(records, key=lambda r: r["timestamp"], reverse=True)
        return [
            EngagementMemoryRecord(
                target_id=r["target_id"],
                action_type=r["action_type"],
                outcome=r["outcome"],
                account_id=r["account_id"],
                timestamp=r["timestamp"],
            )
            for r in sorted_records[:limit]
        ]

    async def store_engagement_outcome(
        self,
        account_id: str,
        target_id: str,
        action_type: str,
        outcome: str,
    ) -> None:
        if account_id not in self._engagements:
            self._engagements[account_id] = []
        self._engagements[account_id].append({
            "target_id": target_id,
            "action_type": action_type,
            "outcome": outcome,
            "account_id": account_id,
            "timestamp": time.time(),
        })
        if outcome == "rejected":
            if account_id not in self._rejections:
                self._rejections[account_id] = set()
            self._rejections[account_id].add(target_id)

    async def recall_rejected_targets(
        self,
        account_id: str,
        limit: int = 50,
    ) -> set[str]:
        return set(list(self._rejections.get(account_id, set()))[:limit])
