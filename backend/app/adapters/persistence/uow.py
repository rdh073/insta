"""In-memory Unit of Work adapter for persistence boundaries."""

from __future__ import annotations

from typing import Optional, Type


class InMemoryPersistenceUoW:
    """No-op transaction adapter with observable commit/rollback semantics."""

    def __init__(self):
        self.begin_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0

    def begin(self) -> None:
        self.begin_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1

    def __enter__(self) -> InMemoryPersistenceUoW:
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
