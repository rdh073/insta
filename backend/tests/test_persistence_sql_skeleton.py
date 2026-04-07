"""Phase 4 durable persistence skeleton tests."""

from __future__ import annotations

import sys
import types
from pathlib import Path

# Minimal shim for backend/state.py import dependency via app.adapters.persistence package.
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

from app.adapters.persistence.repositories import (
    InMemoryAccountRepository,
    InMemoryClientRepository,
    InMemoryJobRepository,
    InMemoryStatusRepository,
)
from app.adapters.persistence.sql_repositories import (
    SqlAccountRepository,
    SqlJobRepository,
    SqlStatusRepository,
)
from app.adapters.persistence.sql_store import SqlitePersistenceStore
from app.adapters.persistence.sql_uow import SqlAlchemyPersistenceUoW
from app.adapters.persistence.factory import build_persistence_adapters
from app.application.ports.persistence_models import AccountRecord, JobRecord
from app.application.use_cases.post_job import CreatePostJobRequest, PostJobUseCases


def test_sql_repositories_roundtrip(tmp_path: Path):
    store = SqlitePersistenceStore(tmp_path / "persistence.sqlite3")
    accounts = SqlAccountRepository(store)
    statuses = SqlStatusRepository(store)
    jobs = SqlJobRepository(store)

    accounts.set("acc-1", AccountRecord(username="operator", password="secret"))
    statuses.set("acc-1", "active")
    jobs.set(
        "job-1",
        JobRecord(
            id="job-1",
            caption="hello",
            status="pending",
            created_at="2026-01-01T00:00:00Z",
        ),
    )

    assert accounts.get("acc-1").username == "operator"
    assert accounts.find_by_username("operator") == "acc-1"
    assert statuses.get("acc-1", "idle") == "active"
    assert jobs.get("job-1").id == "job-1"
    assert len(jobs.list_all()) == 1


def test_sqlalchemy_uow_calls_session_lifecycle(tmp_path: Path):
    store = SqlitePersistenceStore(tmp_path / "uow-lifecycle.sqlite3")
    uow = SqlAlchemyPersistenceUoW(store)
    with uow:
        active = store.get_active_session()
        assert active is not None

    assert store.get_active_session() is None
    assert uow.begin_calls == 1
    assert uow.commit_calls == 1
    assert uow.rollback_calls == 0


def test_build_persistence_adapters_switches_to_sqlite(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
    monkeypatch.setenv("PERSISTENCE_SQLITE_PATH", str(tmp_path / "runtime.sqlite3"))

    account_repo, client_repo, status_repo, job_repo, uow = build_persistence_adapters()

    assert isinstance(account_repo, SqlAccountRepository)
    assert isinstance(client_repo, InMemoryClientRepository)
    assert isinstance(status_repo, SqlStatusRepository)
    assert isinstance(job_repo, SqlJobRepository)
    assert isinstance(uow, SqlAlchemyPersistenceUoW)


def test_build_persistence_adapters_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("PERSISTENCE_BACKEND", raising=False)
    monkeypatch.delenv("PERSISTENCE_SQLITE_PATH", raising=False)

    account_repo, client_repo, status_repo, job_repo, uow = build_persistence_adapters()

    from app.adapters.persistence.uow import InMemoryPersistenceUoW

    assert isinstance(account_repo, InMemoryAccountRepository)
    assert isinstance(client_repo, InMemoryClientRepository)
    assert isinstance(status_repo, InMemoryStatusRepository)
    assert isinstance(job_repo, InMemoryJobRepository)
    assert isinstance(uow, InMemoryPersistenceUoW)


def test_post_job_use_case_works_with_sql_repositories(tmp_path: Path):
    class _StubLogger:
        def log_event(self, *args, **kwargs):
            return None

    store = SqlitePersistenceStore(tmp_path / "persistence.sqlite3")
    account_repo = SqlAccountRepository(store)
    job_repo = SqlJobRepository(store)
    account_repo.set("acc-1", AccountRecord(username="operator"))

    uc = PostJobUseCases(
        job_repo=job_repo,
        account_repo=account_repo,
        logger=_StubLogger(),
        uow=SqlAlchemyPersistenceUoW(store),
    )

    result = uc.create_post_job(
        CreatePostJobRequest(
            caption="hello world",
            account_ids=["acc-1"],
            media_paths=["/tmp/a.jpg"],
        )
    )

    persisted = job_repo.get(result.id)
    assert result.status == "pending"
    assert result.caption == "hello world"
    assert result.results[0]["username"] == "operator"
    assert persisted is not None
    assert persisted.caption == "hello world"


def test_build_persistence_adapters_uses_database_url_env(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "sql")
    monkeypatch.setenv("PERSISTENCE_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.delenv("PERSISTENCE_SQLITE_PATH", raising=False)

    account_repo, client_repo, status_repo, job_repo, uow = build_persistence_adapters()

    assert isinstance(account_repo, SqlAccountRepository)
    assert isinstance(client_repo, InMemoryClientRepository)
    assert isinstance(status_repo, SqlStatusRepository)
    assert isinstance(job_repo, SqlJobRepository)
    assert isinstance(uow, SqlAlchemyPersistenceUoW)
