"""Checkpoint factory adapters for LangGraph workflows."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver


class MemoryCheckpointFactory:
    """Default in-memory checkpointer factory.

    This keeps checkpointer creation in the adapter layer so graph builders
    remain focused on workflow topology instead of persistence concerns.
    """

    def create(self):
        return MemorySaver()

    def create_checkpointer(self):
        return self.create()


class ConfigurableCheckpointFactory:
    """Configurable checkpointer factory for LangGraph workflows.

    Supported backends:
    - ``memory`` (default): in-process state only.
    - ``sqlite``: durable local checkpoint persistence.

    Environment variables:
    - ``LANGGRAPH_CHECKPOINTER_BACKEND``: ``memory`` | ``sqlite``
    - ``LANGGRAPH_CHECKPOINTER_SQLITE_PATH``: sqlite file path for ``sqlite`` backend.
    """

    def __init__(self, backend: str = "memory", sqlite_path: str | None = None):
        self.backend = (backend or "memory").strip().lower()
        self.sqlite_path = sqlite_path

    @classmethod
    def from_env(cls) -> "ConfigurableCheckpointFactory":
        backend = os.getenv("LANGGRAPH_CHECKPOINTER_BACKEND", "memory")
        sqlite_path = os.getenv("LANGGRAPH_CHECKPOINTER_SQLITE_PATH")
        return cls(backend=backend, sqlite_path=sqlite_path)

    def create(self):
        if self.backend == "memory":
            return MemorySaver()

        if self.backend == "sqlite":
            return self._create_sqlite()

        raise RuntimeError(
            "Unsupported LANGGRAPH_CHECKPOINTER_BACKEND. "
            f"Expected 'memory' or 'sqlite', got {self.backend!r}"
        )

    def create_checkpointer(self):
        return self.create()

    async def create_async(self):
        """Create a checkpointer in an async context.

        For the ``sqlite`` backend this creates an ``AsyncSqliteSaver`` (aiosqlite)
        which supports async LangGraph graph calls (``await graph.ainvoke()``).
        The returned saver holds an open aiosqlite connection for the lifetime
        of the process.

        For ``memory`` the result is identical to ``create()``.
        """
        if self.backend == "memory":
            return MemorySaver()
        if self.backend == "sqlite":
            return await self._create_async_sqlite()
        raise RuntimeError(
            "Unsupported LANGGRAPH_CHECKPOINTER_BACKEND. "
            f"Expected 'memory' or 'sqlite', got {self.backend!r}"
        )

    async def _create_async_sqlite(self):
        try:
            import aiosqlite
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        except ImportError as exc:
            raise RuntimeError(
                "SQLite async checkpointer requested but dependency is missing. "
                "Install: langgraph-checkpoint-sqlite aiosqlite"
            ) from exc

        db_path = self.sqlite_path or self._default_sqlite_path()
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(str(db_file))
        return AsyncSqliteSaver(conn)

    def _create_sqlite(self):
        """Sync SQLite checkpointer — only for use cases that run graph.invoke() (sync).

        Note: SqliteSaver does NOT implement async checkpoint methods.
        For async graphs (graph.ainvoke), use create_async() instead.
        """
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:
            raise RuntimeError(
                "SQLite checkpointer backend requested but dependency is missing. "
                "Install: langgraph-checkpoint-sqlite"
            ) from exc

        db_path = self.sqlite_path or self._default_sqlite_path()
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_file), check_same_thread=False)
        return SqliteSaver(conn)

    @staticmethod
    def _default_sqlite_path() -> str:
        backend_root = Path(__file__).resolve().parents[3]
        return str(backend_root / "sessions" / "langgraph_checkpoints.sqlite3")
