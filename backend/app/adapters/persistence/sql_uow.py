"""Durable UoW skeleton for SQL/ORM-based persistence."""

from __future__ import annotations

import threading
from typing import Optional, Type

from sqlalchemy.exc import SQLAlchemyError

from .errors import PersistenceInfrastructureError
from .failure_catalog import build_persistence_failure_message
from .sql_store import SqlitePersistenceStore


class SqlAlchemyPersistenceUoW:
    """SQLAlchemy-backed UoW with shared transactional session.

    Thread safety note
    ------------------
    A single UoW instance is shared across all use cases wired in the
    bootstrap container, but every HTTP request that uses `with self.uow:`
    runs inside its own asyncio.to_thread() worker or event-loop Task.

    Per-scope state (`_session`, `_session_token`, `begin/commit/rollback`
    counters) is therefore kept in `threading.local()`, so concurrent
    requests cannot stomp each other's session tokens. Before this change,
    two concurrent `__enter__()` calls would overwrite the same instance
    attribute, and the later `__exit__()` would hand the wrong
    `contextvars.Token` to `ContextVar.reset()` — which raises
    `ValueError: <Token ... was created in a different Context>` and
    surfaces to the operator as the confusing
    `"Invalid request: <Token var=<ContextVar name='sqlalchemy_persistence_session'...>"`
    message.
    """

    def __init__(self, store: SqlitePersistenceStore):
        self.store = store
        self._local = threading.local()

    # ------------------------------------------------------------------
    # Thread-local scope state
    # ------------------------------------------------------------------

    def _stack(self) -> list[tuple[object, object]]:
        """Return this thread's (session, session_token) stack."""
        stack = getattr(self._local, "stack", None)
        if stack is None:
            stack = []
            self._local.stack = stack
        return stack

    @property
    def session(self):
        """Top session for this thread's current transaction, if any."""
        stack = self._stack()
        return stack[-1][0] if stack else None

    @property
    def _session(self):
        """Back-compat alias for tests that read ``_session`` directly."""
        return self.session

    @property
    def _session_token(self):
        """Back-compat: the ContextVar Token for the topmost scope."""
        stack = self._stack()
        return stack[-1][1] if stack else None

    # ------------------------------------------------------------------
    # Per-thread counters retained for observability/tests
    # ------------------------------------------------------------------

    def _counters(self) -> dict[str, int]:
        counters = getattr(self._local, "counters", None)
        if counters is None:
            counters = {"begin": 0, "commit": 0, "rollback": 0}
            self._local.counters = counters
        return counters

    @property
    def begin_calls(self) -> int:
        return self._counters()["begin"]

    @property
    def commit_calls(self) -> int:
        return self._counters()["commit"]

    @property
    def rollback_calls(self) -> int:
        return self._counters()["rollback"]

    # ------------------------------------------------------------------
    # Transaction lifecycle
    # ------------------------------------------------------------------

    def begin(self) -> None:
        self._counters()["begin"] += 1
        # Only the outermost begin() on this thread opens a new session;
        # nested begin/commit/rollback calls reuse the active one.
        if self._stack():
            return
        try:
            session = self.store.session_factory()
            token = self.store.set_active_session(session)
            session.begin()
        except SQLAlchemyError as exc:
            raise PersistenceInfrastructureError(
                build_persistence_failure_message("uow_begin")
            ) from exc
        except Exception:
            raise
        else:
            self._stack().append((session, token))

    def commit(self) -> None:
        self._counters()["commit"] += 1
        stack = self._stack()
        if not stack:
            return
        session, _token = stack[-1]
        try:
            session.commit()
        except SQLAlchemyError as exc:
            self._close_top_safely()
            raise PersistenceInfrastructureError(
                build_persistence_failure_message("uow_commit")
            ) from exc
        self._close_top()

    def rollback(self) -> None:
        self._counters()["rollback"] += 1
        stack = self._stack()
        if not stack:
            return
        session, _token = stack[-1]
        try:
            session.rollback()
        except SQLAlchemyError as exc:
            self._close_top_safely()
            raise PersistenceInfrastructureError(
                build_persistence_failure_message("uow_rollback")
            ) from exc
        self._close_top()

    def __enter__(self) -> "SqlAlchemyPersistenceUoW":
        self.begin()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb,
    ) -> bool:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False

    # ------------------------------------------------------------------
    # Internal cleanup
    # ------------------------------------------------------------------

    def _close_top(self) -> None:
        stack = self._stack()
        if not stack:
            return
        session, token = stack.pop()
        session.close()
        if token is not None:
            self.store.reset_active_session(token)

    def _close_top_safely(self) -> None:
        stack = self._stack()
        if not stack:
            return
        session, token = stack.pop()
        try:
            session.close()
        finally:
            if token is not None:
                self.store.reset_active_session(token)
