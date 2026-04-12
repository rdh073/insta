"""Phase E runtime smoke tests for persistence backend switching."""

from __future__ import annotations

import sys
import types

import pytest

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

from app.adapters.persistence.factory import build_persistence_adapters
from app.adapters.persistence.post_job_control_adapter import PostJobControlAdapter
from app.application.ports.persistence_models import AccountRecord
from app.application.use_cases.post_job import CreatePostJobRequest, PostJobUseCases
import state as state_module


class _StubLogger:
    def log_event(self, *args, **kwargs):
        return None


def _configure_backend(backend_name: str, monkeypatch, tmp_path) -> None:
    if backend_name == "sqlite":
        monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
        monkeypatch.delenv("PERSISTENCE_DATABASE_URL", raising=False)
        monkeypatch.setenv("PERSISTENCE_SQLITE_PATH", str(tmp_path / "runtime.sqlite3"))
    elif backend_name == "sql_url":
        monkeypatch.setenv("PERSISTENCE_BACKEND", "sql")
        monkeypatch.setenv(
            "PERSISTENCE_DATABASE_URL",
            f"sqlite+pysqlite:///{tmp_path / 'runtime-url.sqlite3'}",
        )
        monkeypatch.delenv("PERSISTENCE_SQLITE_PATH", raising=False)
    else:
        monkeypatch.delenv("PERSISTENCE_BACKEND", raising=False)
        monkeypatch.delenv("PERSISTENCE_DATABASE_URL", raising=False)
        monkeypatch.delenv("PERSISTENCE_SQLITE_PATH", raising=False)
        state_module.clear_state()


@pytest.mark.parametrize("backend_name", ["memory", "sqlite", "sql_url"])
def test_post_job_use_case_smoke_across_persistence_backends(
    backend_name: str,
    monkeypatch,
    tmp_path,
):
    _configure_backend(backend_name, monkeypatch, tmp_path)

    account_repo, _client_repo, _status_repo, job_repo, uow = build_persistence_adapters()
    account_repo.set("acc-1", AccountRecord(username="operator"))

    uc = PostJobUseCases(
        job_repo=job_repo,
        account_repo=account_repo,
        logger=_StubLogger(),
        uow=uow,
    )

    result = uc.create_post_job(
        CreatePostJobRequest(
            caption="runtime smoke",
            account_ids=["acc-1"],
            media_paths=["/tmp/media.jpg"],
            scheduled_at="2026-03-26T15:00:00Z",
        )
    )

    persisted = job_repo.get(result.id)
    assert result.status == "scheduled"
    assert result.results[0]["username"] == "operator"
    assert persisted is not None
    assert persisted.caption == "runtime smoke"
    assert persisted.scheduled_at == "2026-03-26T15:00:00Z"

    # UoW boundary should be exercised regardless of backend choice.
    assert getattr(uow, "begin_calls", 0) >= 1
    assert getattr(uow, "commit_calls", 0) >= 1


@pytest.mark.parametrize("backend_name", ["sqlite", "sql_url"])
@pytest.mark.parametrize("target_status", ["paused", "stopped"])
def test_post_job_control_status_survives_runtime_restart_on_sql_backends(
    backend_name: str,
    target_status: str,
    monkeypatch,
    tmp_path,
):
    _configure_backend(backend_name, monkeypatch, tmp_path)

    account_repo, _client_repo, _status_repo, job_repo, uow = build_persistence_adapters()
    account_repo.set("acc-1", AccountRecord(username="operator"))

    uc = PostJobUseCases(
        job_repo=job_repo,
        account_repo=account_repo,
        logger=_StubLogger(),
        uow=uow,
    )
    created = uc.create_post_job(
        CreatePostJobRequest(
            caption="control smoke",
            account_ids=["acc-1"],
            media_paths=["/tmp/media.jpg"],
        )
    )

    control = PostJobControlAdapter(job_repo=job_repo, uow=uow)
    control.set_job_status(created.id, target_status)

    before_restart = job_repo.get(created.id)
    assert before_restart is not None
    assert before_restart.status == target_status

    # Simulate process restart: in-memory runtime state is gone.
    state_module.job_store.clear()

    after_restart = job_repo.get(created.id)
    assert after_restart is not None
    assert after_restart.status == target_status
