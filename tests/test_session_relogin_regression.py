"""Regression tests for relogin consistency across HTTP, startup, and AI paths."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("fastapi.testclient")

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.main as app_main
from ai_copilot.adapters.account_context_adapter import AccountContextAdapter
from ai_copilot.adapters.recovery_executor_adapter import RecoveryExecutorAdapter
from app.adapters.http.dependencies import get_account_auth_usecases
from app.adapters.http.routers import accounts as accounts_router_module
from app.adapters.http.routers.accounts import router as accounts_router
from app.application.dto.account_dto import AccountResponse
from app.application.ports import ReloginMode
from app.application.use_cases.account.relogin import ReloginUseCases
from app.domain.instagram_failures import InstagramFailure
from app.main import _restore_sessions


class _InMemoryAccountRepo:
    def __init__(self, records: dict[str, dict]):
        self.records = {account_id: dict(data) for account_id, data in records.items()}

    def get(self, account_id: str) -> dict | None:
        record = self.records.get(account_id)
        return dict(record) if record is not None else None

    def update(self, account_id: str, **kwargs) -> None:
        self.records.setdefault(account_id, {}).update(kwargs)

    def exists(self, account_id: str) -> bool:
        return account_id in self.records

    def find_by_username(self, username: str) -> str | None:
        for account_id, record in self.records.items():
            if record.get("username") == username:
                return account_id
        return None

    def list_all_ids(self) -> list[str]:
        return list(self.records.keys())


class _InMemoryStatusRepo:
    def __init__(self, initial: dict[str, str] | None = None):
        self.values = dict(initial or {})
        self.history: list[tuple[str, str]] = []

    def get(self, account_id: str, default: str | None = None) -> str | None:
        return self.values.get(account_id, default)

    def set(self, account_id: str, status: str) -> None:
        self.values[account_id] = status
        self.history.append((account_id, status))


class _RecordingLogger:
    def __init__(self):
        self.events: list[dict] = []

    def log_event(
        self,
        account_id: str,
        username: str,
        event: str,
        detail: str = "",
        status: str = "",
    ) -> None:
        self.events.append(
            {
                "account_id": account_id,
                "username": username,
                "event": event,
                "detail": detail,
                "status": status,
            }
        )


class _FixedFailureHandler:
    def __init__(self, failure: InstagramFailure):
        self.failure = failure

    def handle(self, _exc: Exception, **_kwargs) -> InstagramFailure:
        return self.failure


class _StubInstagramRelogin:
    def __init__(self, *, result: dict | None = None, error: Exception | None = None):
        self._result = result or {"status": "active"}
        self._error = error
        self.calls: list[dict] = []

    def relogin_account(
        self,
        account_id: str,
        *,
        username: str,
        password: str,
        proxy: str | None = None,
        totp_secret: str | None = None,
        mode: ReloginMode = ReloginMode.SESSION_RESTORE,
        **_kwargs,
    ) -> dict:
        self.calls.append(
            {
                "account_id": account_id,
                "username": username,
                "password": password,
                "proxy": proxy,
                "totp_secret": totp_secret,
                "mode": mode,
            }
        )
        if self._error is not None:
            raise self._error
        return dict(self._result)


def _make_accounts_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(accounts_router)
    return app


def _default_failure() -> InstagramFailure:
    return InstagramFailure(
        code="unknown_error",
        family="unknown",
        retryable=False,
        requires_user_action=False,
        user_message="Unknown relogin error",
        http_hint=500,
    )


def _build_relogin_usecase(
    *,
    account_repo: _InMemoryAccountRepo,
    status_repo: _InMemoryStatusRepo,
    instagram: _StubInstagramRelogin,
    logger: _RecordingLogger,
    error_handler: _FixedFailureHandler | None = None,
) -> ReloginUseCases:
    return ReloginUseCases(
        account_repo=account_repo,
        status_repo=status_repo,
        instagram=instagram,
        logger=logger,
        error_handler=error_handler or _FixedFailureHandler(_default_failure()),
    )


def test_relogin_http_success_persists_state_and_schedules_hydration(monkeypatch):
    app = _make_accounts_test_app()
    account_repo = _InMemoryAccountRepo(
        {
            "acc-1": {
                "username": "alice",
                "password": "secret",
                "proxy": "http://proxy:8080",
                "last_error": "Session expired",
                "last_error_code": "login_required",
            }
        }
    )
    status_repo = _InMemoryStatusRepo({"acc-1": "idle"})
    logger = _RecordingLogger()
    instagram = _StubInstagramRelogin(result={"status": "active"})
    relogin = _build_relogin_usecase(
        account_repo=account_repo,
        status_repo=status_repo,
        instagram=instagram,
        logger=logger,
    )

    hydrate_calls: list[str] = []
    monkeypatch.setattr(
        accounts_router_module,
        "_hydrate_and_publish",
        lambda _usecases, account_id: hydrate_calls.append(account_id),
    )
    app.dependency_overrides[get_account_auth_usecases] = lambda: relogin

    with TestClient(app) as client:
        response = client.post("/api/accounts/acc-1/relogin")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "acc-1"
    assert payload["username"] == "alice"
    assert payload["status"] == "active"
    assert payload["lastError"] is None
    assert payload["lastErrorCode"] is None

    assert status_repo.history == [("acc-1", "logging_in"), ("acc-1", "active")]
    assert account_repo.records["acc-1"]["last_error"] is None
    assert account_repo.records["acc-1"]["last_error_code"] is None
    assert hydrate_calls == ["acc-1"]
    assert instagram.calls[0]["mode"] is ReloginMode.FRESH_CREDENTIALS


def test_relogin_http_failure_persists_status_and_returns_structured_error(monkeypatch):
    app = _make_accounts_test_app()
    account_repo = _InMemoryAccountRepo(
        {
            "acc-2": {
                "username": "bob",
                "password": "secret",
                "last_error": None,
                "last_error_code": None,
            }
        }
    )
    status_repo = _InMemoryStatusRepo({"acc-2": "idle"})
    logger = _RecordingLogger()
    instagram = _StubInstagramRelogin(error=RuntimeError("checkpoint"))
    failure = InstagramFailure(
        code="checkpoint_required",
        family="challenge",
        retryable=False,
        requires_user_action=True,
        user_message="Challenge required. Confirm in Instagram app.",
        http_hint=403,
    )
    relogin = _build_relogin_usecase(
        account_repo=account_repo,
        status_repo=status_repo,
        instagram=instagram,
        logger=logger,
        error_handler=_FixedFailureHandler(failure),
    )

    hydrate_calls: list[str] = []
    monkeypatch.setattr(
        accounts_router_module,
        "_hydrate_and_publish",
        lambda _usecases, account_id: hydrate_calls.append(account_id),
    )
    app.dependency_overrides[get_account_auth_usecases] = lambda: relogin

    with TestClient(app) as client:
        response = client.post("/api/accounts/acc-2/relogin")

    assert response.status_code == 403
    assert response.json() == {
        "detail": {
            "message": "Challenge required. Confirm in Instagram app.",
            "code": "checkpoint_required",
            "family": "challenge",
        }
    }
    assert status_repo.history == [("acc-2", "logging_in"), ("acc-2", "challenge")]
    assert account_repo.records["acc-2"]["last_error"] == failure.user_message
    assert account_repo.records["acc-2"]["last_error_code"] == failure.code
    assert hydrate_calls == []


class _StubRestoreAccountRepo:
    def __init__(self, account_ids: list[str]):
        self._account_ids = list(account_ids)

    def list_all_ids(self) -> list[str]:
        return list(self._account_ids)


class _RecordingEventBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def publish(self, event: str, payload: dict) -> None:
        self.events.append((event, dict(payload)))


class _StubHydrateUseCases:
    def __init__(
        self,
        *,
        hydrate_result: dict | None,
        client_exists: bool,
        status: str,
        account: dict,
    ):
        self._hydrate_result = hydrate_result
        self.client_repo = SimpleNamespace(exists=lambda _account_id: client_exists)
        self.status_repo = SimpleNamespace(get=lambda _account_id, _default=None: status)
        self.account_repo = SimpleNamespace(get=lambda _account_id: dict(account))

    def hydrate_account_profile(self, _account_id: str) -> dict | None:
        return self._hydrate_result

    def refresh_follower_counts(self, _account_id: str) -> dict | None:
        return None


@pytest.mark.asyncio
async def test_startup_restore_uses_relogin_result_status_for_publish_and_hydration(monkeypatch):
    done_event = asyncio.Event()
    event_bus = _RecordingEventBus()
    relogin_calls: list[str] = []
    hydrate_calls: list[str] = []

    relogin_results = {
        "acc-active": AccountResponse(id="acc-active", username="alice", status="active"),
        "acc-2fa": AccountResponse(id="acc-2fa", username="bob", status="2fa_required"),
    }

    def relogin_fn(account_id: str):
        relogin_calls.append(account_id)
        if account_id == "acc-challenge":
            raise RuntimeError("challenge")
        return relogin_results[account_id]

    def hydrate_fn(account_id: str):
        hydrate_calls.append(account_id)

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(app_main.asyncio, "sleep", _no_sleep)

    await _restore_sessions(
        account_repo=_StubRestoreAccountRepo(["acc-active", "acc-2fa", "acc-challenge"]),
        relogin_fn=relogin_fn,
        hydrate_fn=hydrate_fn,
        done_event=done_event,
        event_bus=event_bus,
        status_lookup_fn=lambda account_id: {"acc-challenge": "challenge"}.get(
            account_id, "error"
        ),
    )

    assert relogin_calls == ["acc-active", "acc-2fa", "acc-challenge"]
    assert hydrate_calls == ["acc-active"]
    assert event_bus.events == [
        ("account_updated", {"id": "acc-active", "status": "active"}),
        ("account_updated", {"id": "acc-2fa", "status": "2fa_required"}),
        ("account_updated", {"id": "acc-challenge", "status": "challenge"}),
    ]
    assert done_event.is_set() is True


def test_hydrate_and_publish_failure_stream_includes_reason_and_code(monkeypatch):
    event_bus = _RecordingEventBus()
    monkeypatch.setattr(accounts_router_module, "account_event_bus", event_bus)
    usecases = _StubHydrateUseCases(
        hydrate_result=None,
        client_exists=False,
        status="challenge",
        account={
            "last_error": "Challenge required. Confirm in Instagram app.",
            "last_error_code": "checkpoint_required",
        },
    )

    accounts_router_module._hydrate_and_publish(usecases, "acc-1")

    assert event_bus.events == [
        (
            "account_updated",
            {
                "id": "acc-1",
                "status": "challenge",
                "last_error": "Challenge required. Confirm in Instagram app.",
                "last_error_code": "checkpoint_required",
            },
        )
    ]


@pytest.mark.asyncio
async def test_startup_restore_not_active_publish_includes_reason_and_code(monkeypatch):
    done_event = asyncio.Event()
    event_bus = _RecordingEventBus()

    def relogin_fn(_account_id: str):
        return AccountResponse(
            id="acc-2fa",
            username="bob",
            status="2fa_required",
            last_error="2FA required. Enter the code manually.",
            last_error_code="two_factor_required",
        )

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(app_main.asyncio, "sleep", _no_sleep)

    await _restore_sessions(
        account_repo=_StubRestoreAccountRepo(["acc-2fa"]),
        relogin_fn=relogin_fn,
        done_event=done_event,
        event_bus=event_bus,
    )

    assert event_bus.events == [
        (
            "account_updated",
            {
                "id": "acc-2fa",
                "status": "2fa_required",
                "last_error": "2FA required. Enter the code manually.",
                "last_error_code": "two_factor_required",
            },
        )
    ]
    assert done_event.is_set() is True


@pytest.mark.asyncio
async def test_startup_restore_exception_publish_includes_structured_failure(monkeypatch):
    done_event = asyncio.Event()
    event_bus = _RecordingEventBus()
    failure = InstagramFailure(
        code="checkpoint_required",
        family="challenge",
        retryable=False,
        requires_user_action=True,
        user_message="Challenge required. Confirm in Instagram app.",
        http_hint=403,
    )

    def relogin_fn(_account_id: str):
        exc = RuntimeError("checkpoint")
        exc._instagram_failure = failure  # type: ignore[attr-defined]
        raise exc

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(app_main.asyncio, "sleep", _no_sleep)

    await _restore_sessions(
        account_repo=_StubRestoreAccountRepo(["acc-challenge"]),
        relogin_fn=relogin_fn,
        done_event=done_event,
        event_bus=event_bus,
        status_lookup_fn=lambda _account_id: "challenge",
    )

    assert event_bus.events == [
        (
            "account_updated",
            {
                "id": "acc-challenge",
                "status": "challenge",
                "last_error": "Challenge required. Confirm in Instagram app.",
                "last_error_code": "checkpoint_required",
            },
        )
    ]
    assert done_event.is_set() is True


class _StubAccountService:
    def __init__(self, relogin_result):
        self._relogin_result = relogin_result
        self.calls: list[str] = []

    def get_accounts_summary(self) -> dict:
        return {"accounts": []}

    def relogin_account(self, account_id: str):
        self.calls.append(account_id)
        if isinstance(self._relogin_result, Exception):
            raise self._relogin_result
        return self._relogin_result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("relogin_result", "expected"),
    [
        (AccountResponse(id="acc-1", username="alice", status="active"), True),
        ({"status": "active"}, True),
        ({"status": "2fa_required"}, False),
    ],
)
async def test_account_context_try_refresh_session_status_contract(
    relogin_result, expected
):
    adapter = AccountContextAdapter(account_service=_StubAccountService(relogin_result))
    assert await adapter.try_refresh_session("acc-1") is expected


@pytest.mark.asyncio
async def test_account_context_try_refresh_session_returns_false_on_exception():
    adapter = AccountContextAdapter(
        account_service=_StubAccountService(RuntimeError("session refresh failed"))
    )
    assert await adapter.try_refresh_session("acc-1") is False


class _StubRecoveryAccountUseCases:
    def __init__(self):
        self.username_map: dict[str, str] = {}
        self.account_ids: list[str] = []
        self.relogin_result = AccountResponse(id="acc-1", username="alice", status="active")
        self.relogin_error: Exception | None = None
        self.relogin_calls: list[str] = []

    def find_by_username(self, username: str) -> str | None:
        return self.username_map.get(username)

    def list_accounts(self):
        return [SimpleNamespace(id=account_id) for account_id in self.account_ids]

    def relogin_account(self, account_id: str):
        self.relogin_calls.append(account_id)
        if self.relogin_error is not None:
            raise self.relogin_error
        return self.relogin_result

    def set_account_proxy(self, account_id: str, proxy: str):
        return {"id": account_id, "proxy": proxy}


@pytest.mark.asyncio
async def test_recovery_executor_relogin_resolves_username_and_reports_success():
    usecases = _StubRecoveryAccountUseCases()
    usecases.username_map = {"alice": "acc-1"}
    usecases.relogin_result = AccountResponse(id="acc-1", username="alice", status="active")
    adapter = RecoveryExecutorAdapter(usecases)

    result = await adapter.relogin("alice")

    assert result == {"success": True, "requires_2fa": False, "error": None}
    assert usecases.relogin_calls == ["acc-1"]


@pytest.mark.asyncio
async def test_recovery_executor_relogin_maps_2fa_status_and_not_found():
    usecases = _StubRecoveryAccountUseCases()
    usecases.account_ids = ["acc-2"]
    usecases.relogin_result = AccountResponse(id="acc-2", username="bob", status="2fa_required")
    adapter = RecoveryExecutorAdapter(usecases)

    needs_2fa = await adapter.relogin("acc-2")
    missing = await adapter.relogin("missing")

    assert needs_2fa == {
        "success": False,
        "requires_2fa": True,
        "error": "status: 2fa_required",
    }
    assert missing == {
        "success": False,
        "requires_2fa": False,
        "error": "Account not found: missing",
    }


@pytest.mark.asyncio
async def test_recovery_executor_relogin_classifies_exception_as_2fa_when_hint_present():
    usecases = _StubRecoveryAccountUseCases()
    usecases.account_ids = ["acc-3"]
    usecases.relogin_error = RuntimeError("verification code required")
    adapter = RecoveryExecutorAdapter(usecases)

    result = await adapter.relogin("acc-3")

    assert result["success"] is False
    assert result["requires_2fa"] is True
    assert "verification code required" in result["error"]
