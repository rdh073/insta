"""Phase 2 persistence Unit of Work contracts."""

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

from app.adapters.persistence.uow import InMemoryPersistenceUoW
from app.application.ports.persistence_models import AccountRecord
from app.application.use_cases.account import AccountUseCases
from app.application.use_cases.post_job import CreatePostJobRequest, PostJobUseCases


class _StubJobRepo:
    def __init__(self):
        self.jobs = {}

    def get(self, job_id: str):
        return self.jobs.get(job_id)

    def set(self, job_id: str, job):
        self.jobs[job_id] = job

    def list_all(self):
        return list(self.jobs.values())


class _StubAccountRepo:
    def __init__(self):
        self.accounts = {"acc-1": AccountRecord(username="operator")}

    def get(self, account_id: str):
        return self.accounts.get(account_id)

    def find_by_username(self, username: str):
        for account_id, record in self.accounts.items():
            if record.username == username:
                return account_id
        return None

    def list_all_ids(self):
        return list(self.accounts.keys())

    def exists(self, account_id: str) -> bool:
        return account_id in self.accounts

    def set(self, account_id: str, data):
        self.accounts[account_id] = data

    def update(self, account_id: str, **kwargs):
        record = self.accounts.get(account_id)
        if record is None:
            return
        for key, value in kwargs.items():
            setattr(record, key, value)

    def remove(self, account_id: str):
        self.accounts.pop(account_id, None)


class _StubLogger:
    def log_event(self, *args, **kwargs):
        return None


class _StubClient:
    def __init__(self, fail_proxy: bool = False):
        self.fail_proxy = fail_proxy

    def set_proxy(self, proxy: str):
        if self.fail_proxy:
            raise RuntimeError("proxy update failed")


class _StubClientRepo:
    def __init__(self, client=None):
        self.client = client

    def get(self, account_id: str):
        return self.client

    def set(self, account_id: str, client):
        self.client = client

    def remove(self, account_id: str):
        out = self.client
        self.client = None
        return out

    def exists(self, account_id: str) -> bool:
        return self.client is not None

    def list_active_ids(self):
        return ["acc-1"] if self.client is not None else []


class _StubStatusRepo:
    def __init__(self):
        self.values = {}

    def get(self, account_id: str, default=None):
        return self.values.get(account_id, default)

    def set(self, account_id: str, status: str):
        self.values[account_id] = status

    def clear(self, account_id: str):
        self.values.pop(account_id, None)


class _StubInstagram:
    def create_authenticated_client(
        self,
        username: str,
        password: str,
        proxy=None,
        totp_secret=None,
        verify_session: bool = False,
    ):
        return _StubClient()

    def complete_2fa(self, username: str, password: str, code: str, proxy=None):
        return _StubClient()

    def relogin_account(self, account_id: str):
        return {"id": account_id, "username": "operator", "status": "active"}


class _StubTotp:
    def normalize_secret(self, secret: str):
        return secret

    def generate_code(self, secret: str):
        return "123456"

    def verify_code(self, secret: str, code: str):
        return True

    def generate_secret(self):
        return "SECRET"

    def get_provisioning_uri(self, secret: str, username: str):
        return "otpauth://example"


class _StubSessionStore:
    def save_session(self, username: str, session_data: dict):
        return None

    def load_session(self, username: str) -> dict:
        return {}

    def export_all_sessions(self) -> dict:
        return {}

    def import_sessions(self, sessions: dict) -> None:
        return None


class _StubErrorHandler:
    class _Failure:
        def __init__(self):
            self.code = "unknown"
            self.user_message = "error"

    def handle(self, exc, **kwargs):
        return self._Failure()


class _StubIdentityReader:
    def get_authenticated_account(self, account_id: str):
        raise RuntimeError("not used")

    def get_public_user_by_id(self, account_id: str, user_id: int):
        raise RuntimeError("not used")

    def get_public_user_by_username(self, account_id: str, username: str):
        raise RuntimeError("not used")


def test_inmemory_uow_commits_on_success():
    uow = InMemoryPersistenceUoW()

    with uow:
        pass

    assert uow.begin_calls == 1
    assert uow.commit_calls == 1
    assert uow.rollback_calls == 0


def test_inmemory_uow_rolls_back_on_error():
    uow = InMemoryPersistenceUoW()

    with pytest.raises(RuntimeError):
        with uow:
            raise RuntimeError("boom")

    assert uow.begin_calls == 1
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1


def test_post_job_write_path_uses_uow_commit():
    uow = InMemoryPersistenceUoW()
    uc = PostJobUseCases(
        job_repo=_StubJobRepo(),
        account_repo=_StubAccountRepo(),
        logger=_StubLogger(),
        uow=uow,
    )

    uc.create_post_job(
        CreatePostJobRequest(
            caption="hello",
            account_ids=["acc-1"],
            media_paths=["/tmp/pic.jpg"],
        )
    )

    assert uow.begin_calls == 1
    assert uow.commit_calls == 1
    assert uow.rollback_calls == 0


def test_post_job_write_path_uses_uow_rollback_on_error():
    class _FailingAccountRepo(_StubAccountRepo):
        def get(self, account_id: str):
            raise RuntimeError("account load failed")

    uow = InMemoryPersistenceUoW()
    uc = PostJobUseCases(
        job_repo=_StubJobRepo(),
        account_repo=_FailingAccountRepo(),
        logger=_StubLogger(),
        uow=uow,
    )

    with pytest.raises(RuntimeError):
        uc.create_post_job(
            CreatePostJobRequest(
                caption="hello",
                account_ids=["acc-1"],
                media_paths=["/tmp/pic.jpg"],
            )
        )

    assert uow.begin_calls == 1
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1


def test_account_proxy_update_uses_uow_commit_and_rollback():
    # Commit path
    uow_ok = InMemoryPersistenceUoW()
    account_repo_ok = _StubAccountRepo()
    uc_ok = AccountUseCases(
        account_repo=account_repo_ok,
        client_repo=_StubClientRepo(client=_StubClient(fail_proxy=False)),
        status_repo=_StubStatusRepo(),
        instagram=_StubInstagram(),
        logger=_StubLogger(),
        totp=_StubTotp(),
        session_store=_StubSessionStore(),
        error_handler=_StubErrorHandler(),
        identity_reader=_StubIdentityReader(),
        uow=uow_ok,
    )
    uc_ok.set_account_proxy("acc-1", "http://proxy:8000")
    assert uow_ok.commit_calls == 1
    assert uow_ok.rollback_calls == 0

    # Rollback path
    uow_fail = InMemoryPersistenceUoW()
    account_repo_fail = _StubAccountRepo()
    uc_fail = AccountUseCases(
        account_repo=account_repo_fail,
        client_repo=_StubClientRepo(client=_StubClient(fail_proxy=True)),
        status_repo=_StubStatusRepo(),
        instagram=_StubInstagram(),
        logger=_StubLogger(),
        totp=_StubTotp(),
        session_store=_StubSessionStore(),
        error_handler=_StubErrorHandler(),
        identity_reader=_StubIdentityReader(),
        uow=uow_fail,
    )
    with pytest.raises(RuntimeError):
        uc_fail.set_account_proxy("acc-1", "http://proxy:9000")
    assert uow_fail.commit_calls == 0
    assert uow_fail.rollback_calls == 1
