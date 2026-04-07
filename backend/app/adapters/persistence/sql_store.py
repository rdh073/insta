"""SQLAlchemy persistence store primitives for durable persistence.

Implements production-grade connection management:
  - Connection pool configuration with NullPool for SQLite safety
  - ContextVar-based session tracking for transaction boundaries
  - Schema version checking for migration safety
  - Explicit begin/commit/rollback semantics for failure clarity

This store is adapter-facing only; application/use-cases must depend
on ports/repositories, not this class directly.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path
from typing import Iterator

from sqlalchemy import (
    Boolean,
    Float,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


class AccountRow(Base):
    """Account persistence row."""

    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    password: Mapped[str] = mapped_column(Text, default="", nullable=False)
    proxy: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    following: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AccountStatusRow(Base):
    """Account status persistence row."""

    __tablename__ = "account_status"

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)


class JobRow(Base):
    """Post-job persistence row."""

    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    caption: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    media_type: Mapped[str] = mapped_column(String(64), default="photo", nullable=False)
    scheduled_at: Mapped[str | None] = mapped_column(String(128), nullable=True)
    targets: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    results: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    media_urls: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    media_paths: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    igtv_title: Mapped[str | None] = mapped_column(Text, nullable=True)



class ProxyRow(Base):
    """Proxy pool persistence row — stores only elite, working proxies."""

    __tablename__ = "proxies"
    __table_args__ = (UniqueConstraint("host", "port", name="uq_proxy_host_port"),)

    id:         Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    host:       Mapped[str]   = mapped_column(String(255), nullable=False)
    port:       Mapped[int]   = mapped_column(Integer, nullable=False)
    protocol:   Mapped[str]   = mapped_column(String(16), nullable=False)
    anonymity:  Mapped[str]   = mapped_column(String(16), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    url:        Mapped[str]   = mapped_column(Text, nullable=False)


class AlembicVersion(Base):
    """Track Alembic migration version (for startup validation)."""

    __tablename__ = "alembic_version"

    version_num: Mapped[str] = mapped_column(String(32), primary_key=True)

class SqlitePersistenceStore:
    """Owns SQLAlchemy engine/session lifecycle for SQL persistence adapters."""

    def __init__(self, db_path: Path | None = None, database_url: str | None = None):
        """Initialize SQL persistence store with production-grade connection management.

        Args:
            db_path: Path to SQLite database file (fallback to default if not provided).
            database_url: Full SQLAlchemy connection URL (takes precedence).

        Connection pool strategy:
          - SQLite: NullPool (no connection pooling, safer for file-based concurrency)
          - PostgreSQL/MySQL: QueuePool (connection pooling for production)
          - Timeout: 30s connection timeout (configurable via PERSISTENCE_CONN_TIMEOUT)
        """
        if database_url:
            self.database_url = database_url
        else:
            assert db_path is not None
            db_file = Path(db_path)
            db_file.parent.mkdir(parents=True, exist_ok=True)
            self.database_url = f"sqlite:///{db_file}"

        # Determine connection pool class based on database type
        is_sqlite = self.database_url.startswith("sqlite://")
        pool_class = NullPool if is_sqlite else QueuePool

        # Create engine with connection-level guards
        # NullPool for SQLite: no connection caching (each use gets a fresh connection)
        # QueuePool for PostgreSQL/MySQL: bounded connection pool
        engine_kwargs = {
            "future": True,
            "poolclass": pool_class,
            "echo": False,  # Set to True for SQL debug logging
        }

        if not is_sqlite:
            # Production database: add pool size and timeout
            pool_size = _env_int("PERSISTENCE_POOL_SIZE", 10)
            max_overflow = _env_int("PERSISTENCE_MAX_OVERFLOW", 20)
            pool_timeout = _env_int("PERSISTENCE_POOL_TIMEOUT_SECONDS", 30)
            engine_kwargs["pool_size"] = max(1, pool_size)
            engine_kwargs["max_overflow"] = max(0, max_overflow)
            engine_kwargs["pool_timeout"] = max(1, pool_timeout)

        self.engine = create_engine(self.database_url, **engine_kwargs)

        # Configure connection timeout for SQLite (file locking)
        if is_sqlite:
            sqlite_busy_timeout_ms = max(1000, _env_int("PERSISTENCE_SQLITE_BUSY_TIMEOUT_MS", 5000))

            @event.listens_for(self.engine, "connect")
            def _set_sqlite_pragma(dbapi_conn, connection_record):
                """Set SQLite pragmas for safety and performance."""
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
                cursor.execute("PRAGMA synchronous=NORMAL")  # Balance safety/speed
                cursor.execute(f"PRAGMA busy_timeout={sqlite_busy_timeout_ms}")
                cursor.close()

        self._session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self._active_session: ContextVar[object | None] = ContextVar(
            "sqlalchemy_persistence_session",
            default=None,
        )
        self._ensure_schema()

    @property
    def session_factory(self):
        return self._session_factory

    def get_active_session(self):
        return self._active_session.get()

    def set_active_session(self, session):
        return self._active_session.set(session)

    def reset_active_session(self, token) -> None:
        self._active_session.reset(token)

    @contextmanager
    def session_scope(self) -> Iterator:
        """Yield a session, reusing active UoW session when available."""
        active = self.get_active_session()
        if active is not None:
            yield active
            return

        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def check_schema_version(self, expected_version: str | None = None) -> str | None:
        """Check if schema is at expected version (optional startup validation).
        
        Args:
            expected_version: If provided, verify schema is at this version.
                             Raises RuntimeError if mismatch detected.
        
        Returns:
            Current alembic_version if it exists, None otherwise.
        
        Raises:
            RuntimeError: If schema version mismatch detected when expected_version is set.
        """
        try:
            with self.session_scope() as session:
                result = session.query(AlembicVersion).first()
                current_version = result.version_num if result else None
                
                if expected_version and current_version != expected_version:
                    raise RuntimeError(
                        f"Schema version mismatch: expected {expected_version}, "
                        f"got {current_version}. Run migrations: alembic upgrade head"
                    )
                
                return current_version
        except Exception as e:
            # If alembic_version table doesn't exist yet (fresh db),
            # it's not an error for optional checks
            if "no such table" in str(e).lower() or "does not exist" in str(e).lower():
                return None
            raise

    def ping(self) -> None:
        """Verify the configured database accepts a lightweight query."""
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def _ensure_schema(self) -> None:
        Base.metadata.create_all(self.engine)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return default
