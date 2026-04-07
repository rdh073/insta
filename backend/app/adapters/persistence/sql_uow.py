"""Durable UoW skeleton for SQL/ORM-based persistence."""

from __future__ import annotations

from typing import Optional, Type

from sqlalchemy.exc import SQLAlchemyError

from .errors import PersistenceInfrastructureError
from .failure_catalog import build_persistence_failure_message
from .sql_store import SqlitePersistenceStore


class SqlAlchemyPersistenceUoW:
    """SQLAlchemy-backed UoW with shared transactional session."""

    def __init__(self, store: SqlitePersistenceStore):
        self.store = store
        self._session = None
        self._session_token = None
        self.begin_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0

    @property
    def session(self):
        return self._session

    def begin(self) -> None:
        self.begin_calls += 1
        if self._session is None:
            try:
                self._session = self.store.session_factory()
                self._session_token = self.store.set_active_session(self._session)
                self._session.begin()
            except SQLAlchemyError as exc:
                self._close_session_safely()
                raise PersistenceInfrastructureError(
                    build_persistence_failure_message("uow_begin")
                ) from exc

    def commit(self) -> None:
        self.commit_calls += 1
        if self._session is not None:
            try:
                self._session.commit()
            except SQLAlchemyError as exc:
                self._close_session_safely()
                raise PersistenceInfrastructureError(
                    build_persistence_failure_message("uow_commit")
                ) from exc
            self._close_session()

    def rollback(self) -> None:
        self.rollback_calls += 1
        if self._session is not None:
            try:
                self._session.rollback()
            except SQLAlchemyError as exc:
                self._close_session_safely()
                raise PersistenceInfrastructureError(
                    build_persistence_failure_message("uow_rollback")
                ) from exc
            self._close_session()

    def __enter__(self) -> SqlAlchemyPersistenceUoW:
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

    def _close_session(self) -> None:
        self._session.close()
        if self._session_token is not None:
            self.store.reset_active_session(self._session_token)
            self._session_token = None
        self._session = None

    def _close_session_safely(self) -> None:
        if self._session is None:
            return
        try:
            self._session.close()
        finally:
            if self._session_token is not None:
                self.store.reset_active_session(self._session_token)
                self._session_token = None
            self._session = None
