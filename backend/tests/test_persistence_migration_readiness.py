"""Phase 4: Migration-aware startup checks for production persistence.

Tests verify:
  - Schema version validation at startup
  - Alembic migration tracking
  - Migration failure handling
  - Rollback safety semantics
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

# Minimal shim for backend/state.py import dependency
if "instagrapi" not in sys.modules:
    instagrapi_module = types.ModuleType("instagrapi")
    exceptions_module = types.ModuleType("instagrapi.exceptions")

    class _StubClient:  # pragma: no cover - shim class
        pass

    class _StubException(Exception):  # pragma: no cover - shim class
        pass

    instagrapi_module.Client = _StubClient
    exceptions_module.LoginRequired = _StubException
    exceptions_module.BadPassword = _StubException
    exceptions_module.ReloginAttemptExceeded = _StubException
    exceptions_module.TwoFactorRequired = _StubException
    instagrapi_module.exceptions = exceptions_module
    sys.modules["instagrapi"] = instagrapi_module
    sys.modules["instagrapi.exceptions"] = exceptions_module

from app.adapters.persistence.sql_store import SqlitePersistenceStore


class TestMigrationReadiness:
    """Verify migration governance and schema validation."""

    def test_sqlite_store_initializes_schema(self, tmp_path):
        """Schema must be created automatically on first init."""
        db_path = tmp_path / "test.sqlite3"
        store = SqlitePersistenceStore(db_path=db_path)

        # Verify database file created
        assert db_path.exists()

        # Verify schema inspection (tables exist)
        with store.session_scope() as session:
            inspector = __import__("sqlalchemy", fromlist=["inspect"]).inspect
            insp = inspector(store.engine)
            tables = insp.get_table_names()
            assert "accounts" in tables
            assert "account_status" in tables
            assert "jobs" in tables

    def test_accounts_schema_includes_last_error_family_column(self, tmp_path, monkeypatch):
        """Schema migrations must include accounts.last_error_family."""
        db_path = tmp_path / "test_health_column.sqlite3"
        monkeypatch.setenv("PERSISTENCE_DATABASE_URL", f"sqlite:///{db_path}")
        store = SqlitePersistenceStore(db_path=db_path)

        inspector = __import__("sqlalchemy", fromlist=["inspect"]).inspect
        columns = {column["name"] for column in inspector(store.engine).get_columns("accounts")}
        assert "last_error_family" in columns

    def test_schema_version_check_optional(self, tmp_path):
        """Schema version check should be optional (backward compat)."""
        db_path = tmp_path / "test_version.sqlite3"
        store = SqlitePersistenceStore(db_path=db_path)

        # Calling check_schema_version with no arg should not fail
        # (alembic_version table may not exist yet)
        result = store.check_schema_version()
        assert result is None or isinstance(result, str)

    def test_schema_version_mismatch_raises_error(self, tmp_path):
        """Schema version mismatch should raise RuntimeError when expected version set."""
        db_path = tmp_path / "test_mismatch.sqlite3"
        store = SqlitePersistenceStore(db_path=db_path)

        # Calling with expected version should fail if alembic_version not set
        with pytest.raises(RuntimeError, match="Schema version mismatch"):
            store.check_schema_version(expected_version="001_baseline_schema")

    def test_uow_transaction_semantics_on_error(self, tmp_path, monkeypatch):
        """UoW must rollback on exception (not commit)."""
        monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
        monkeypatch.setenv("PERSISTENCE_DATABASE_URL", f"sqlite:///{tmp_path / 'test_uow.sqlite3'}")

        from app.adapters.persistence.factory import build_persistence_adapters
        from app.application.ports.persistence_models import AccountRecord

        accts, _, _, _, uow = build_persistence_adapters()

        # Set up initial state
        accts.set("acc-1", AccountRecord(username="test_user"))

        # Simulate transaction error
        with pytest.raises(RuntimeError, match="Simulated error"):
            with uow:
                # Within UoW transaction
                accts.set("acc-2", AccountRecord(username="should_not_persist"))
                raise RuntimeError("Simulated error")

        # Verify acc-2 was NOT persisted (rollback happened)
        persisted = accts.get("acc-2")
        assert persisted is None, "Account persisted despite rollback"

    def test_uow_commit_on_success(self, tmp_path, monkeypatch):
        """UoW must commit on successful exit."""
        monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
        monkeypatch.setenv("PERSISTENCE_DATABASE_URL", f"sqlite:///{tmp_path / 'test_commit.sqlite3'}")

        from app.adapters.persistence.factory import build_persistence_adapters
        from app.application.ports.persistence_models import AccountRecord

        accts, _, _, _, uow = build_persistence_adapters()

        # Successful transaction
        with uow:
            accts.set("acc-1", AccountRecord(username="committed_user"))

        # Verify commit happened
        persisted = accts.get("acc-1")
        assert persisted is not None
        assert persisted.username == "committed_user"

    def test_concurrent_uow_isolation(self, tmp_path, monkeypatch):
        """Multiple UoW instances should isolate transactions."""
        monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
        monkeypatch.setenv("PERSISTENCE_DATABASE_URL", f"sqlite:///{tmp_path / 'test_iso.sqlite3'}")

        from app.adapters.persistence.factory import build_persistence_adapters
        from app.application.ports.persistence_models import AccountRecord

        accts1, _, _, _, uow1 = build_persistence_adapters()
        # Second factory call returns separate adapters (not shared session)
        accts2, _, _, _, uow2 = build_persistence_adapters()

        # UoW1 writes and commits
        with uow1:
            accts1.set("acc-iso", AccountRecord(username="isolated"))

        # UoW2 should see the committed data
        persisted = accts2.get("acc-iso")
        assert persisted is not None
        assert persisted.username == "isolated"


class TestMigrationRollbackSafety:
    """Verify that rollback paths are safe (no data loss)."""

    def test_rollback_preserves_prior_state(self, tmp_path, monkeypatch):
        """Rollback must not corrupt or lose committed data."""
        db_path = tmp_path / "test_rollback.sqlite3"
        monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
        monkeypatch.setenv("PERSISTENCE_DATABASE_URL", f"sqlite:///{db_path}")

        from app.adapters.persistence.factory import build_persistence_adapters
        from app.application.ports.persistence_models import AccountRecord

        # Initial state: add account
        accts, _, _, _, _ = build_persistence_adapters()
        accts.set("rollback-test", AccountRecord(username="original"))

        # Verify it's there
        original = accts.get("rollback-test")
        assert original.username == "original"

        # Simulate failure and rollback (factory rebuild = new store instance)
        accts2, _, _, _, uow2 = build_persistence_adapters()

        # Try transaction that fails
        try:
            with uow2:
                accts2.set("rollback-test", AccountRecord(username="modified"))
                raise RuntimeError("Forced rollback")
        except RuntimeError:
            pass

        # Original data should still be there (rollback prevented update)
        accts3, _, _, _, _ = build_persistence_adapters()
        final = accts3.get("rollback-test")
        # Behavior depends on whether the failed UoW had already written:
        # In SQLAlchemy with explicit rollback, the original should remain
        assert final is not None, "Data was lost during rollback"
        assert final.username == "original", "Rollback did not protect prior state"
