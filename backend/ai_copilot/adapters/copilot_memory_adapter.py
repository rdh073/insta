"""Copilot memory adapter — implements CopilotMemoryPort using LangGraph Store.

Stores interaction summaries so the planner has continuity across sessions.
Nodes access this through the port interface, never the Store directly.

Namespace layout:
    (operator_namespace, "interactions") → past copilot run summaries
"""

from __future__ import annotations

import logging
import time
import uuid

from ai_copilot.application.ports import CopilotMemoryPort

logger = logging.getLogger(__name__)


class LangGraphCopilotMemoryAdapter(CopilotMemoryPort):
    """Cross-thread copilot memory backed by a LangGraph Store."""

    def __init__(self, store):
        self._store = store

    async def recall_recent_interactions(
        self,
        namespace: str,
        limit: int = 5,
    ) -> list[dict]:
        ns = (namespace, "interactions")
        try:
            items = await self._store.asearch(ns, limit=limit)
            records = [item.value for item in items]
            records.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
            return records[:limit]
        except Exception:
            logger.exception("Failed to recall copilot interactions for ns=%s", namespace)
            return []

    async def store_interaction_summary(
        self,
        namespace: str,
        summary: dict,
    ) -> None:
        ns = (namespace, "interactions")
        record_id = str(uuid.uuid4())
        if "timestamp" not in summary:
            summary["timestamp"] = time.time()
        try:
            await self._store.aput(ns, record_id, summary)
            logger.debug("Stored copilot interaction ns=%s goal=%s", namespace, summary.get("goal", "")[:60])
        except Exception:
            logger.exception("Failed to store copilot interaction ns=%s", namespace)


class InMemoryCopilotMemoryAdapter(CopilotMemoryPort):
    """Simple in-memory implementation for testing (no LangGraph dependency)."""

    def __init__(self):
        self._interactions: dict[str, list[dict]] = {}

    async def recall_recent_interactions(
        self,
        namespace: str,
        limit: int = 5,
    ) -> list[dict]:
        records = self._interactions.get(namespace, [])
        sorted_records = sorted(records, key=lambda r: r.get("timestamp", 0), reverse=True)
        return sorted_records[:limit]

    async def store_interaction_summary(
        self,
        namespace: str,
        summary: dict,
    ) -> None:
        if "timestamp" not in summary:
            summary["timestamp"] = time.time()
        if namespace not in self._interactions:
            self._interactions[namespace] = []
        self._interactions[namespace].append(dict(summary))
