"""Persistence adapter factory with backend feature flag selection.

Implements config priority for production readiness:
  1. PERSISTENCE_DATABASE_URL (production override, no default)
  2. PERSISTENCE_SQLITE_PATH (explicit sqlite file path)
  3. Default sqlite path: backend/sessions/persistence.sqlite3
  4. Memory backend (default, no persistence)

Connection-level guards:
  - SQLAlchemy connection pool with NullPool for safety
  - Session scope management via ContextVar for transaction safety
  - Explicit begin/commit/rollback semantics for failure path clarity
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from .repositories import (
    InMemoryAccountRepository,
    InMemoryClientRepository,
    InMemoryStatusRepository,
    InMemoryJobRepository,
    InMemoryProxyRepository,
    InMemoryTemplateRepository,
)
from .sql_store import SqlitePersistenceStore
from .sql_repositories import SqlAccountRepository, SqlStatusRepository, SqlJobRepository, SqlProxyRepository, SqlTemplateRepository
from .smart_engagement_repositories import (
    SqlSmartEngagementApprovalRepository,
    SqlSmartEngagementAuditLogRepository,
)
from .uow import InMemoryPersistenceUoW
from .sql_uow import SqlAlchemyPersistenceUoW


def current_persistence_backend() -> str:
    """Return the normalized persistence backend name."""
    return os.getenv("PERSISTENCE_BACKEND", "memory").strip().lower()


@lru_cache(maxsize=None)
def _build_sql_persistence_store_cached(
    persistence_backend: str,
    database_url: str | None,
    sqlite_path: str | None,
) -> SqlitePersistenceStore | None:
    """Build a SQL persistence store for a specific backend configuration."""
    if persistence_backend not in {"sqlite", "sql"}:
        return None

    if database_url:
        return SqlitePersistenceStore(database_url=database_url)

    assert sqlite_path is not None
    return SqlitePersistenceStore(db_path=Path(sqlite_path))


def build_sql_persistence_store() -> SqlitePersistenceStore | None:
    """Build (and cache) a SQL persistence store for the active env configuration.

    The cache key includes backend + connection inputs so runtime backend switches
    in tests do not reuse stale stores from a previous configuration.
    """
    persistence_backend = current_persistence_backend()
    database_url = os.getenv("PERSISTENCE_DATABASE_URL")
    default_db_path = Path(__file__).parent.parent.parent.parent / "sessions" / "persistence.sqlite3"
    sqlite_path = os.getenv("PERSISTENCE_SQLITE_PATH", str(default_db_path))
    return _build_sql_persistence_store_cached(persistence_backend, database_url, sqlite_path)


def build_persistence_adapters():
    """Build persistence adapters based on backend configuration.

    Returns:
        Tuple of (AccountRepository, ClientRepository, StatusRepository, JobRepository, UoW)

    Raises:
        RuntimeError: If SQL backend is selected but database configuration is invalid.
    """
    sql_store = build_sql_persistence_store()

    if sql_store is not None:
        return (
            SqlAccountRepository(sql_store),
            InMemoryClientRepository(),
            SqlStatusRepository(sql_store),
            SqlJobRepository(sql_store),
            SqlAlchemyPersistenceUoW(sql_store),
        )

    # Default: in-memory persistence (no durability, safe for testing)
    return (
        InMemoryAccountRepository(),
        InMemoryClientRepository(),
        InMemoryStatusRepository(),
        InMemoryJobRepository(),
        InMemoryPersistenceUoW(),
    )


def build_proxy_repository():
    """Build proxy repository based on backend configuration.

    Returns SQL-backed SqlProxyRepository when PERSISTENCE_BACKEND=sqlite or sql,
    otherwise returns InMemoryProxyRepository (non-persistent, useful for tests).
    """
    sql_store = build_sql_persistence_store()
    if sql_store is not None:
        return SqlProxyRepository(sql_store)

    return InMemoryProxyRepository()


def build_llm_config_repository():
    """Build LLM config repository based on backend configuration.

    Returns SQL-backed repository when PERSISTENCE_BACKEND=sqlite or sql,
    otherwise returns in-memory repository (not persistent).

    Returns:
        LLMConfigRepository implementation.
    """
    from .llm_config_inmemory import InMemoryLLMConfigRepository

    if current_persistence_backend() in {"sqlite", "sql"}:
        try:
            from .crypto import CryptoService
            from .llm_config_repository import SQLLLMConfigRepository

            sql_store = build_sql_persistence_store()
            assert sql_store is not None

            crypto = CryptoService()
            return SQLLLMConfigRepository(sql_store, crypto)
        except RuntimeError:
            # ENCRYPTION_KEY not set — fall back to in-memory with a warning
            import warnings
            warnings.warn(
                "ENCRYPTION_KEY env var not set. LLM configs will not be persisted. "
                "Set ENCRYPTION_KEY to enable SQL persistence for LLM configs.",
                stacklevel=2,
            )
            return InMemoryLLMConfigRepository()

    return InMemoryLLMConfigRepository()


def build_template_repository():
    """Build template repository based on backend configuration."""
    sql_store = build_sql_persistence_store()
    if sql_store is not None:
        return SqlTemplateRepository(sql_store)
    return InMemoryTemplateRepository()


def build_smart_engagement_repositories():
    """Build smart-engagement SQL repositories when DB persistence is active.

    Returns:
        tuple(approval_repo, audit_repo) on SQL backends, otherwise (None, None).
    """
    sql_store = build_sql_persistence_store()
    if sql_store is None:
        return None, None
    return (
        SqlSmartEngagementApprovalRepository(sql_store),
        SqlSmartEngagementAuditLogRepository(sql_store),
    )


def build_oauth_token_store():
    """Build OAuth token store with durable SQL when enabled.

    Priority:
      1. SQL + encryption (when PERSISTENCE_BACKEND=sqlite/sql and ENCRYPTION_KEY set)
      2. SQL without encryption → warns and falls back to file store
      3. Memory backend → file store (sessions/oauth_tokens.json, no env vars needed)

    The file store ensures OAuth tokens survive process restarts without requiring
    any environment variable configuration.
    """
    from .oauth_token_store_file import FileOAuthTokenStore

    if current_persistence_backend() in {"sqlite", "sql"}:
        try:
            from .crypto import CryptoService
            from .oauth_token_store_repository import SQLOAuthTokenStore

            sql_store = build_sql_persistence_store()
            assert sql_store is not None

            crypto = CryptoService()
            return SQLOAuthTokenStore(sql_store, crypto)
        except RuntimeError:
            import warnings

            warnings.warn(
                "ENCRYPTION_KEY env var not set. OAuth credentials will be stored unencrypted "
                "in the file store (sessions/oauth_tokens.json). Set ENCRYPTION_KEY to enable "
                "encrypted SQL persistence for OAuth refresh tokens.",
                stacklevel=2,
            )
            return FileOAuthTokenStore()

    return FileOAuthTokenStore()
