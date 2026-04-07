"""Phase 3 state gateway compatibility tests."""

from __future__ import annotations

import json
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

from app.adapters.persistence.activity_log import ActivityLogWriter
from app.adapters.persistence.repositories import (
    InMemoryAccountRepository,
    InMemoryClientRepository,
    InMemoryJobRepository,
    InMemoryStatusRepository,
)
from app.adapters.persistence.session_store import SessionStore
from app.application.ports.persistence_models import AccountRecord, JobRecord


class _StubGateway:
    def __init__(self, sessions_dir: Path):
        self._accounts: dict[str, dict] = {}
        self._clients: dict[str, object] = {}
        self._statuses: dict[str, str] = {}
        self._jobs: dict[str, dict] = {}
        self.logged: list[tuple[str, str, str, str, str]] = []
        self.sessions_dir = sessions_dir

    def get_account(self, account_id: str):
        return self._accounts.get(account_id)

    def has_account(self, account_id: str) -> bool:
        return account_id in self._accounts

    def set_account(self, account_id: str, data: dict) -> None:
        self._accounts[account_id] = data

    def update_account(self, account_id: str, **kwargs) -> None:
        if account_id in self._accounts:
            self._accounts[account_id].update(kwargs)

    def pop_account(self, account_id: str):
        return self._accounts.pop(account_id, None)

    def find_account_id_by_username(self, username: str):
        for account_id, account in self._accounts.items():
            if account.get("username") == username:
                return account_id
        return None

    def account_ids(self):
        return list(self._accounts.keys())

    def iter_account_items(self):
        return list(self._accounts.items())

    def get_client(self, account_id: str):
        return self._clients.get(account_id)

    def set_client(self, account_id: str, client) -> None:
        self._clients[account_id] = client

    def pop_client(self, account_id: str):
        return self._clients.pop(account_id, None)

    def has_client(self, account_id: str) -> bool:
        return account_id in self._clients

    def active_client_ids(self):
        return list(self._clients.keys())

    def get_account_status_value(self, account_id: str, default: str = "idle"):
        return self._statuses.get(account_id, default)

    def set_account_status(self, account_id: str, status: str) -> None:
        self._statuses[account_id] = status

    def clear_account_status(self, account_id: str) -> None:
        self._statuses.pop(account_id, None)

    def get_job(self, job_id: str):
        return self._jobs.get(job_id)

    def set_job(self, job_id: str, job: dict) -> None:
        self._jobs[job_id] = job

    def iter_jobs_values(self):
        return list(self._jobs.values())

    def log_event(self, account_id: str, username: str, event: str, *, detail: str = "", status: str = "") -> None:
        self.logged.append((account_id, username, event, detail, status))


def test_repositories_work_with_injected_state_gateway(tmp_path: Path):
    gateway = _StubGateway(tmp_path)
    accounts = InMemoryAccountRepository(gateway=gateway)
    clients = InMemoryClientRepository(gateway=gateway)
    statuses = InMemoryStatusRepository(gateway=gateway)
    jobs = InMemoryJobRepository(gateway=gateway)

    accounts.set("acc-1", AccountRecord(username="operator"))
    assert accounts.get("acc-1").username == "operator"
    assert accounts.find_by_username("operator") == "acc-1"
    assert accounts.list_all_ids() == ["acc-1"]

    clients.set("acc-1", object())
    assert clients.exists("acc-1") is True
    assert clients.list_active_ids() == ["acc-1"]

    statuses.set("acc-1", "active")
    assert statuses.get("acc-1") == "active"
    statuses.clear("acc-1")
    assert statuses.get("acc-1", "idle") == "idle"

    jobs.set(
        "job-1",
        JobRecord(
            id="job-1",
            caption="hello",
            status="pending",
            created_at="2026-01-01T00:00:00Z",
        ),
    )
    assert jobs.get("job-1").id == "job-1"
    assert len(jobs.list_all()) == 1


def test_activity_log_and_session_store_use_gateway(tmp_path: Path):
    gateway = _StubGateway(tmp_path)
    log = ActivityLogWriter(gateway=gateway)
    sessions = SessionStore(gateway=gateway)

    log.log_event("acc-1", "operator", "login_success", detail="ok", status="active")
    assert gateway.logged == [("acc-1", "operator", "login_success", "ok", "active")]

    payload = {"sessionid": "abc123"}
    sessions.save_session("operator", payload)
    loaded = sessions.load_session("operator")
    assert loaded == payload
    raw = (tmp_path / "operator.json").read_text()
    assert json.loads(raw)["sessionid"] == "abc123"
