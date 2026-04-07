"""Phase 1 persistence repository contracts.

Ensures in-memory persistence adapters expose typed records instead of raw dicts.
"""

from __future__ import annotations

import sys
import types

# Minimal shim for backend/state.py import dependency.
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
from app.application.ports.persistence_models import AccountRecord, JobRecord
import state as state_module


def setup_function():
    state_module.clear_state()


def test_account_repository_roundtrip_returns_account_record():
    repo = InMemoryAccountRepository()
    repo.set(
        "acc-1",
        AccountRecord(
            username="operator",
            password="secret",
            proxy="http://proxy:8000",
            full_name="Operator",
            followers=120,
            following=10,
        ),
    )

    record = repo.get("acc-1")

    assert isinstance(record, AccountRecord)
    assert record is not None
    assert record.username == "operator"
    assert record.full_name == "Operator"
    assert record.followers == 120


def test_account_repository_supports_update_iter_and_remove():
    repo = InMemoryAccountRepository()
    repo.set("acc-1", AccountRecord(username="operator", proxy="http://old-proxy"))

    repo.update("acc-1", proxy="http://new-proxy", full_name="Operator Name")
    updated = repo.get("acc-1")

    assert updated is not None
    assert updated.proxy == "http://new-proxy"
    assert updated.full_name == "Operator Name"
    assert repo.find_by_username("operator") == "acc-1"

    all_rows = repo.iter_all()
    assert len(all_rows) == 1
    assert all_rows[0][0] == "acc-1"
    assert isinstance(all_rows[0][1], AccountRecord)

    repo.remove("acc-1")
    assert repo.get("acc-1") is None
    assert repo.list_all_ids() == []


def test_job_repository_roundtrip_returns_job_record():
    repo = InMemoryJobRepository()
    repo.set(
        "job-1",
        JobRecord(
            id="job-1",
            caption="hello world",
            status="pending",
            targets=[{"accountId": "acc-1"}],
            results=[{"accountId": "acc-1", "status": "pending"}],
            created_at="2026-01-01T00:00:00Z",
            media_urls=["/tmp/media.jpg"],
            media_type="photo",
            media_paths=["/tmp/media.jpg"],
        ),
    )

    job = repo.get("job-1")
    jobs = repo.list_all()

    assert isinstance(job, JobRecord)
    assert job is not None
    assert job.id == "job-1"
    assert job.caption == "hello world"
    assert len(jobs) == 1
    assert isinstance(jobs[0], JobRecord)


def test_client_repository_roundtrip_and_active_ids():
    repo = InMemoryClientRepository()
    client_obj = object()
    assert repo.exists("acc-1") is False

    repo.set("acc-1", client_obj)
    assert repo.exists("acc-1") is True
    assert repo.get("acc-1") is client_obj
    assert repo.list_active_ids() == ["acc-1"]

    removed = repo.remove("acc-1")
    assert removed is client_obj
    assert repo.exists("acc-1") is False
    assert repo.list_active_ids() == []


def test_status_repository_default_set_and_clear():
    repo = InMemoryStatusRepository()
    assert repo.get("acc-1") == "idle"
    assert repo.get("acc-1", default="unknown") == "unknown"

    repo.set("acc-1", "active")
    assert repo.get("acc-1") == "active"

    repo.clear("acc-1")
    assert repo.get("acc-1") == "idle"
