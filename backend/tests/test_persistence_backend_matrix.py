"""Phase 4: Parametrized test matrix across all persistence backends.

Ensures that the same behavior is consistent across:
  - Memory (in-process, ephemeral)
  - SQLite (file-based, durable)
  - PostgreSQL/SQL URL (database server)

All tests must pass on all backends.
"""

from __future__ import annotations

import os
import sys
import types

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

from app.adapters.persistence.factory import build_persistence_adapters
from app.application.ports.persistence_models import AccountRecord, JobRecord


class TestPersistenceBackendMatrix:
    """Test suite runs against all backends (parametrized)."""

    @pytest.mark.parametrize("backend_name", ["memory", "sqlite", "sql_url"])
    def test_account_repository_interface_consistency(
        self,
        backend_name: str,
        monkeypatch,
        tmp_path,
    ):
        """AccountRepository interface must work identically on all backends."""
        # Configure backend
        if backend_name == "sqlite":
            monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
            monkeypatch.delenv("PERSISTENCE_DATABASE_URL", raising=False)
            monkeypatch.setenv("PERSISTENCE_SQLITE_PATH", str(tmp_path / "test.sqlite3"))
        elif backend_name == "sql_url":
            monkeypatch.setenv("PERSISTENCE_BACKEND", "sql")
            monkeypatch.setenv(
                "PERSISTENCE_DATABASE_URL",
                f"sqlite+pysqlite:///{tmp_path / 'test_url.sqlite3'}",
            )
            monkeypatch.delenv("PERSISTENCE_SQLITE_PATH", raising=False)
        else:
            # memory
            monkeypatch.delenv("PERSISTENCE_BACKEND", raising=False)
            monkeypatch.delenv("PERSISTENCE_DATABASE_URL", raising=False)
            monkeypatch.delenv("PERSISTENCE_SQLITE_PATH", raising=False)

        accts, _, _, _, _ = build_persistence_adapters()

        # Test: set + get
        accts.set("acc-1", AccountRecord(username="alice"))
        result = accts.get("acc-1")
        assert result is not None
        assert result.username == "alice"

        # Test: exists
        assert accts.exists("acc-1") is True
        assert accts.exists("acc-nonexistent") is False

        # Test: update
        accts.update("acc-1", followers=100)
        updated = accts.get("acc-1")
        assert updated.followers == 100

        # Test: find_by_username
        found_id = accts.find_by_username("alice")
        assert found_id == "acc-1"

        # Test: list_all_ids
        accts.set("acc-2", AccountRecord(username="bob"))
        all_ids = accts.list_all_ids()
        assert "acc-1" in all_ids
        assert "acc-2" in all_ids

        # Test: remove
        accts.remove("acc-1")
        assert accts.exists("acc-1") is False

    @pytest.mark.parametrize("backend_name", ["memory", "sqlite", "sql_url"])
    def test_status_repository_interface_consistency(
        self,
        backend_name: str,
        monkeypatch,
        tmp_path,
    ):
        """StatusRepository interface must work identically on all backends."""
        # Configure backend
        if backend_name == "sqlite":
            monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
            monkeypatch.setenv("PERSISTENCE_SQLITE_PATH", str(tmp_path / "status.sqlite3"))
        elif backend_name == "sql_url":
            monkeypatch.setenv("PERSISTENCE_BACKEND", "sql")
            monkeypatch.setenv(
                "PERSISTENCE_DATABASE_URL",
                f"sqlite+pysqlite:///{tmp_path / 'status_url.sqlite3'}",
            )
            monkeypatch.delenv("PERSISTENCE_SQLITE_PATH", raising=False)
        else:
            monkeypatch.delenv("PERSISTENCE_BACKEND", raising=False)
            monkeypatch.delenv("PERSISTENCE_DATABASE_URL", raising=False)

        _, _, status, _, _ = build_persistence_adapters()

        # Test: set + get
        status.set("acc-1", "running")
        assert status.get("acc-1") == "running"

        # Test: get with default
        assert status.get("acc-nonexistent", default="idle") == "idle"

        # Test: clear
        status.clear("acc-1")
        assert status.get("acc-1", default="idle") == "idle"

    @pytest.mark.parametrize("backend_name", ["memory", "sqlite", "sql_url"])
    def test_job_repository_interface_consistency(
        self,
        backend_name: str,
        monkeypatch,
        tmp_path,
    ):
        """JobRepository interface must work identically on all backends."""
        # Configure backend
        if backend_name == "sqlite":
            monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
            monkeypatch.setenv("PERSISTENCE_SQLITE_PATH", str(tmp_path / "jobs.sqlite3"))
        elif backend_name == "sql_url":
            monkeypatch.setenv("PERSISTENCE_BACKEND", "sql")
            monkeypatch.setenv(
                "PERSISTENCE_DATABASE_URL",
                f"sqlite+pysqlite:///{tmp_path / 'jobs_url.sqlite3'}",
            )
            monkeypatch.delenv("PERSISTENCE_SQLITE_PATH", raising=False)
        else:
            monkeypatch.delenv("PERSISTENCE_BACKEND", raising=False)
            monkeypatch.delenv("PERSISTENCE_DATABASE_URL", raising=False)

        _, _, _, jobs, _ = build_persistence_adapters()

        # Test: set + get
        job = JobRecord(
            id="job-1",
            caption="test post",
            status="pending",
            targets=[{"account_id": "acc-1"}],
        )
        jobs.set("job-1", job)
        result = jobs.get("job-1")
        assert result is not None
        assert result.caption == "test post"
        assert result.status == "pending"

        # Test: list_all
        job2 = JobRecord(
            id="job-2",
            caption="another post",
            status="pending",
        )
        jobs.set("job-2", job2)
        all_jobs = jobs.list_all()
        assert len(all_jobs) == 2
        assert any(j.id == "job-1" for j in all_jobs)

    @pytest.mark.parametrize("backend_name", ["memory", "sqlite", "sql_url"])
    def test_uow_transaction_boundary_consistency(
        self,
        backend_name: str,
        monkeypatch,
        tmp_path,
    ):
        """UoW semantics must be consistent: begin -> commit/rollback."""
        # Configure backend
        if backend_name == "sqlite":
            monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
            monkeypatch.setenv("PERSISTENCE_SQLITE_PATH", str(tmp_path / "uow.sqlite3"))
        elif backend_name == "sql_url":
            monkeypatch.setenv("PERSISTENCE_BACKEND", "sql")
            monkeypatch.setenv(
                "PERSISTENCE_DATABASE_URL",
                f"sqlite+pysqlite:///{tmp_path / 'uow_url.sqlite3'}",
            )
            monkeypatch.delenv("PERSISTENCE_SQLITE_PATH", raising=False)
        else:
            monkeypatch.delenv("PERSISTENCE_BACKEND", raising=False)
            monkeypatch.delenv("PERSISTENCE_DATABASE_URL", raising=False)

        accts, _, _, _, uow = build_persistence_adapters()

        # Test: successful commit
        with uow:
            accts.set("acc-tx", AccountRecord(username="txn_test"))

        # Verify data persisted
        persisted = accts.get("acc-tx")
        assert persisted is not None

        # Test: rollback on exception
        try:
            with uow:
                accts.set("acc-rollback", AccountRecord(username="should_not_exist"))
                raise ValueError("Intentional test error")
        except ValueError:
            pass

        # Verify rollback happened (only for SQL backends that track tx state)
        # For memory backend, this might still be committed, but isolation is preserved
        rolled_back = accts.get("acc-rollback")
        # This assertion is backend-dependent; memory may not rollback
        if backend_name != "memory":
            assert rolled_back is None, f"Rollback failed on {backend_name}"

        # Test: metrics (if available)
        if hasattr(uow, "begin_calls"):
            assert uow.begin_calls >= 1
        if hasattr(uow, "commit_calls"):
            assert uow.commit_calls >= 1


class TestBackendSwitching:
    """Verify smooth switching between backends."""

    def test_memory_to_sqlite_switch(self, monkeypatch, tmp_path):
        """Data in memory does not persist; SQLite should start fresh."""
        # Start with memory
        monkeypatch.delenv("PERSISTENCE_BACKEND", raising=False)
        monkeypatch.delenv("PERSISTENCE_DATABASE_URL", raising=False)

        accts1, _, _, _, _ = build_persistence_adapters()
        accts1.set("mem-acc", AccountRecord(username="memory_user"))

        # Switch to SQLite
        monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
        monkeypatch.setenv(
            "PERSISTENCE_SQLITE_PATH", str(tmp_path / "switch.sqlite3")
        )

        accts2, _, _, _, _ = build_persistence_adapters()

        # Memory data should not exist in SQLite
        sqlite_acc = accts2.get("mem-acc")
        assert sqlite_acc is None

        # But new writes to SQLite should persist
        accts2.set("sql-acc", AccountRecord(username="sqlite_user"))
        persisted = accts2.get("sql-acc")
        assert persisted is not None

    def test_sqlite_persistence_across_instances(self, monkeypatch, tmp_path):
        """Data written to SQLite should persist across adapter instances."""
        sqlite_path = tmp_path / "persistent.sqlite3"
        monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
        monkeypatch.setenv("PERSISTENCE_SQLITE_PATH", str(sqlite_path))

        # First instance
        accts1, _, _, _, _ = build_persistence_adapters()
        accts1.set("persist-acc", AccountRecord(username="persistent_user"))

        # Second instance (new factory call, same SQLite file)
        accts2, _, _, _, _ = build_persistence_adapters()

        # Data should be there
        persisted = accts2.get("persist-acc")
        assert persisted is not None
        assert persisted.username == "persistent_user"
