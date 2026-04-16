"""Tests for the Instagram challenge resolver port, adapter, use case,
HTTP router, bootstrap wiring, and AI tool policy classification.

Covered scenarios:

1. Resolver adapter in isolation — submit_code unblocks the seated hook.
2. Timeout — no submit produces ChallengeTimeoutError and clears the entry.
3. Cancel — cancel() unblocks the hook with ChallengeCancelledError.
4. Integration via AccountAuthUseCases — login blocks in the SDK hook, a
   submit_code from another thread unblocks it, and the account ends up
   status="active".
5. HTTP router — GET/POST/DELETE endpoints exercised via TestClient.
6. Policy parity — list_pending_challenges is READ_ONLY and no submit_code
   tool is registered with the AI layer.
7. Bootstrap — the HTTP router and AuthUseCases share the same resolver
   instance and the hook seated into instagrapi is the very same one.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.adapters.http.dependencies import (
    get_account_challenge_usecases,
    get_account_repo,
)
from app.adapters.instagram.challenge_resolver import (
    ChallengeCancelledError,
    ChallengeTimeoutError,
    InstagramChallengeResolverAdapter,
)
from app.application.dto.account_dto import LoginRequest
from app.application.use_cases.account.challenge import ChallengeUseCases
from app.application.use_cases.account_auth import AccountAuthUseCases
from app.main import app

from ai_copilot.application.operator_copilot_policy import (
    ToolPolicy,
    ToolPolicyRegistry,
)


# ── 1. Resolver adapter — submit unblocks the hook ──────────────────────────


def test_resolver_submit_code_unblocks_hook_and_returns_code():
    resolver = InstagramChallengeResolverAdapter(default_timeout_seconds=5.0)
    resolver.register_account("acc-1", "alice")
    result: dict = {}

    def _hook_caller() -> None:
        try:
            result["code"] = resolver.handle_challenge_code_request(
                "alice", type("_Choice", (), {"name": "EMAIL"})()
            )
        except Exception as exc:  # pragma: no cover - defensive
            result["error"] = exc

    worker = threading.Thread(target=_hook_caller, daemon=True)
    worker.start()

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not resolver.has_pending("acc-1"):
        time.sleep(0.01)

    assert resolver.has_pending("acc-1"), "hook must publish a pending entry"
    pending = resolver.get_pending("acc-1")
    assert pending is not None and pending.method == "EMAIL"

    resolution = resolver.submit_code("acc-1", "123456")
    worker.join(timeout=2.0)

    assert not worker.is_alive()
    assert resolution.status == "resolved"
    assert resolution.next_step == "relogin"
    assert result.get("code") == "123456"
    assert not resolver.has_pending("acc-1")


# ── 2. Resolver adapter — timeout surfaces as ChallengeTimeoutError ─────────


def test_resolver_raises_timeout_when_no_code_submitted():
    resolver = InstagramChallengeResolverAdapter(default_timeout_seconds=0.2)
    resolver.register_account("acc-2", "bob")

    with pytest.raises(ChallengeTimeoutError):
        resolver.handle_challenge_code_request("bob", None)

    assert not resolver.has_pending("acc-2")


# ── 3. Resolver adapter — cancel unblocks with ChallengeCancelledError ──────


def test_resolver_cancel_unblocks_hook_with_cancellation_error():
    resolver = InstagramChallengeResolverAdapter(default_timeout_seconds=5.0)
    resolver.register_account("acc-3", "carol")
    result: dict = {}

    def _hook_caller() -> None:
        try:
            resolver.handle_challenge_code_request("carol", None)
        except ChallengeCancelledError as exc:
            result["error"] = exc

    worker = threading.Thread(target=_hook_caller, daemon=True)
    worker.start()

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not resolver.has_pending("acc-3"):
        time.sleep(0.01)
    assert resolver.has_pending("acc-3")

    resolution = resolver.cancel("acc-3")
    worker.join(timeout=2.0)

    assert not worker.is_alive()
    assert resolution.status == "cancelled"
    assert isinstance(result.get("error"), ChallengeCancelledError)
    assert not resolver.has_pending("acc-3")


# ── 4. Integration — login flow blocks, submit_code drives it to active ─────


class _FakeAccountRepo:
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}

    def find_by_username(self, username):
        for aid, rec in self.records.items():
            if rec.get("username") == username:
                return aid
        return None

    def set(self, account_id, record):
        data = (
            record.__dict__
            if hasattr(record, "__dict__")
            else dict(record) if isinstance(record, dict) else {}
        )
        # AccountRecord is a dataclass; copy relevant fields
        if hasattr(record, "username"):
            data = {
                "username": record.username,
                "password": record.password,
                "proxy": record.proxy,
                "country": record.country,
                "country_code": record.country_code,
                "locale": record.locale,
                "timezone_offset": record.timezone_offset,
                "totp_secret": record.totp_secret,
            }
        self.records[account_id] = dict(data)

    def get(self, account_id):
        return self.records.get(account_id)

    def exists(self, account_id):
        return account_id in self.records

    def update(self, account_id, **kwargs):
        if account_id in self.records:
            self.records[account_id].update(kwargs)

    def remove(self, account_id):
        self.records.pop(account_id, None)


class _FakeClientRepo:
    def __init__(self) -> None:
        self._clients: dict[str, object] = {}

    def set(self, account_id, client):
        self._clients[account_id] = client

    def exists(self, account_id):
        return account_id in self._clients

    def remove(self, account_id):
        return self._clients.pop(account_id, None)


class _FakeStatusRepo:
    def __init__(self) -> None:
        self._statuses: dict[str, str] = {}

    def set(self, account_id, status):
        self._statuses[account_id] = status

    def get(self, account_id, default=None):
        return self._statuses.get(account_id, default)

    def clear(self, account_id):
        self._statuses.pop(account_id, None)


def _make_auth_usecases(instagram, resolver):
    """Assemble AccountAuthUseCases with lightweight doubles."""
    totp = Mock()
    totp.normalize_secret.side_effect = lambda s: s

    identity_reader = Mock()
    identity_reader.get_authenticated_account.side_effect = Exception("skip")

    return AccountAuthUseCases(
        account_repo=_FakeAccountRepo(),
        client_repo=_FakeClientRepo(),
        status_repo=_FakeStatusRepo(),
        instagram=instagram,
        logger=Mock(),
        totp=totp,
        session_store=Mock(),
        error_handler=Mock(),
        identity_reader=identity_reader,
        challenge_resolver=resolver,
    )


def test_login_end_to_end_resolves_challenge_and_returns_active():
    resolver = InstagramChallengeResolverAdapter(default_timeout_seconds=5.0)
    captured: dict[str, str] = {}

    class _FakeIG:
        def create_authenticated_client(
            self, username, password, proxy, totp_secret=None, **_kw
        ):
            # Simulate instagrapi's SDK invoking challenge_code_handler while
            # it is resolving a server-side challenge.
            choice = type("_Choice", (), {"name": "EMAIL"})()
            code = resolver.handle_challenge_code_request(username, choice)
            captured["code"] = code
            return object()  # fake signed-in client

        def complete_2fa(self, *_a, **_kw):  # pragma: no cover - unused
            raise AssertionError("2fa path not expected")

        def relogin_account(self, *_a, **_kw):  # pragma: no cover - unused
            raise AssertionError("relogin path not expected")

    usecases = _make_auth_usecases(_FakeIG(), resolver)

    login_result: dict = {}

    def _run_login() -> None:
        try:
            login_result["value"] = usecases.login_account(
                LoginRequest(username="alice", password="hunter2")
            )
        except Exception as exc:  # pragma: no cover - surface failure
            login_result["error"] = exc

    worker = threading.Thread(target=_run_login, daemon=True)
    worker.start()

    # Wait for the pending entry to appear.
    deadline = time.monotonic() + 3.0
    pending_list: list = []
    while time.monotonic() < deadline:
        pending_list = resolver.list_pending()
        if pending_list:
            break
        time.sleep(0.01)
    assert pending_list, "resolver should surface a pending challenge"
    assert pending_list[0].username == "alice"

    resolution = resolver.submit_code(pending_list[0].account_id, "654321")
    assert resolution.status == "resolved"

    worker.join(timeout=3.0)
    assert not worker.is_alive()
    assert captured.get("code") == "654321"

    result = login_result.get("value")
    assert result is not None, login_result.get("error")
    assert result.status == "active"
    assert not resolver.has_pending(pending_list[0].account_id)


# ── 5. HTTP router — pending/submit/cancel endpoints ────────────────────────


class _StubChallengeUseCases:
    """In-memory double matching ChallengeUseCases' public contract."""

    def __init__(self) -> None:
        from app.application.dto.instagram_challenge_dto import (
            ChallengePending,
            ChallengeResolution,
        )

        self._Pending = ChallengePending
        self._Resolution = ChallengeResolution
        self._store: dict[str, ChallengePending] = {}

    def seed(self, pending) -> None:
        self._store[pending.account_id] = pending

    def list_pending(self):
        return list(self._store.values())

    def get(self, account_id):
        return self._store.get(account_id)

    def submit_code(self, account_id, code):
        if not code.strip():
            return self._Resolution(
                account_id=account_id,
                status="failed",
                message="empty code",
                next_step="manual",
            )
        self._store.pop(account_id, None)
        return self._Resolution(
            account_id=account_id,
            status="resolved",
            message="ok",
            next_step="relogin",
        )

    def cancel(self, account_id):
        self._store.pop(account_id, None)
        return self._Resolution(
            account_id=account_id,
            status="cancelled",
            message="cancelled",
            next_step="manual",
        )


def test_router_exposes_challenge_endpoints_end_to_end():
    from app.application.dto.instagram_challenge_dto import ChallengePending

    stub = _StubChallengeUseCases()
    stub.seed(
        ChallengePending(
            account_id="acc-7",
            username="dave",
            method="EMAIL",
            contact_hint="d***@example.com",
            created_at="2026-04-16T00:00:00+00:00",
        )
    )

    stub_account_repo = Mock()
    stub_account_repo.exists.return_value = True

    app.dependency_overrides[get_account_challenge_usecases] = lambda: stub
    app.dependency_overrides[get_account_repo] = lambda: stub_account_repo

    try:
        with TestClient(app) as http:
            resp = http.get("/api/accounts/challenges/pending")
            assert resp.status_code == 200
            assert resp.json() == [
                {
                    "account_id": "acc-7",
                    "username": "dave",
                    "method": "EMAIL",
                    "contact_hint": "d***@example.com",
                    "created_at": "2026-04-16T00:00:00+00:00",
                }
            ]

            resp = http.get("/api/accounts/acc-7/challenge")
            assert resp.status_code == 200
            assert resp.json()["username"] == "dave"

            resp = http.get("/api/accounts/acc-missing/challenge")
            assert resp.status_code == 204
            assert resp.content == b""

            resp = http.post(
                "/api/accounts/acc-7/challenge/submit", json={"code": "654321"}
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "resolved"

            # Cancel on an empty store still returns 204 per contract.
            resp = http.delete("/api/accounts/acc-7/challenge")
            assert resp.status_code == 204
    finally:
        app.dependency_overrides.pop(get_account_challenge_usecases, None)
        app.dependency_overrides.pop(get_account_repo, None)


# ── 6. Policy parity — tool is READ_ONLY and no submit_code tool exists ─────


def test_policy_classifies_list_pending_challenges_read_only():
    registry = ToolPolicyRegistry()

    classification = registry.classify("list_pending_challenges")
    assert classification.policy is ToolPolicy.READ_ONLY
    assert classification.requires_approval is False


def test_ai_tool_registry_exposes_list_pending_challenges_and_hides_submit_code():
    from app.adapters.ai.tool_registry.builder import (
        list_registered_tool_names_for_policy_audit,
    )

    tool_names = set(list_registered_tool_names_for_policy_audit())
    assert "list_pending_challenges" in tool_names
    assert "submit_challenge_code" not in tool_names
    assert "submit_code" not in tool_names


# ── 7. Bootstrap wiring — single shared resolver instance ───────────────────


def test_bootstrap_shares_one_challenge_resolver_instance():
    from app.adapters.http.dependencies import get_services
    from app.adapters.instagram.challenge_resolver import get_current_resolver

    # Invalidate any cached container from earlier tests so we observe wiring
    # freshly (create_services wires the hook every call).
    get_services.cache_clear()

    services = get_services()
    resolver = services["challenge_resolver"]

    # Same instance reachable from HTTP router, AuthUseCases, and the seated
    # SDK hook.
    assert services["account_challenge"]._resolver is resolver
    assert services["account_auth"].challenge_resolver is resolver
    assert get_current_resolver() is resolver
