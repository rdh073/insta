"""Persistence Unit of Work port (Phase 0 frozen contract).

PersistenceUnitOfWork is a production-grade contract for transaction boundaries.
Changes to this interface must be approved via architecture review and validated
across all persistence backend implementations (memory, sqlite, sql).
"""

from __future__ import annotations

from typing import Optional, Protocol, Type


class PersistenceUnitOfWork(Protocol):
    """Application-facing transaction boundary contract."""

    def begin(self) -> None:
        """Begin a transaction scope."""
        ...

    def commit(self) -> None:
        """Commit successful transaction scope."""
        ...

    def rollback(self) -> None:
        """Rollback failed transaction scope."""
        ...

    def __enter__(self) -> PersistenceUnitOfWork:
        """Enter transactional context."""
        ...

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb,
    ) -> bool:
        """Exit transactional context."""
        ...
