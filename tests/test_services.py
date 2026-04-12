from __future__ import annotations

import asyncio
import json

import instagram
import pytest
import services
import state
from services_focused import account_auth as account_auth_runtime


class FakeUser:
    username = "alice"
    full_name = "Alice Example"
    biography = "bio"
    follower_count = 123
    following_count = 45
    media_count = 6
    is_private = False
    is_verified = False
    is_business = True


class FakeClient:
    def __init__(self):
        self.user_id = "user-1"
        self.proxy = None
        self.loaded_settings = None
        self.request_timeout = 60
        self.delay_range = [1, 3]

    def set_proxy(self, proxy: str):
        self.proxy = proxy

    def set_device(self, _device: dict) -> None:
        pass

    def set_user_agent(self, _ua: str) -> None:
        pass

    def load_settings(self, path):
        self.loaded_settings = path

    def login(self, username: str, password: str, **kwargs):
        self.username = username
        self.password = password

    def dump_settings(self, path):
        path.write_text(json.dumps({"session": self.username}))

    def user_info(self, _user_id: str):
        return FakeUser()

    def logout(self):
        self.logged_out = True


def test_login_account_persists_session_and_updates_state(monkeypatch):
    monkeypatch.setattr(instagram, "IGClient", FakeClient)

    result = services.login_account("alice", "secret", "http://proxy:8080")

    assert result["username"] == "alice"
    assert result["status"] == "active"
    # followers enrichment happens via background task, not during login_account itself

    account_id = result["id"]
    assert (state.get_account(account_id) or {})["proxy"] == "http://proxy:8080"
    assert state.get_account_status_value(account_id) == "active"
    assert isinstance(state.get_client(account_id), FakeClient)
    assert (services.SESSIONS_DIR / "alice.json").exists()


def test_login_account_enables_verify_session_policy_for_restore_path(monkeypatch):
    captured: list[bool] = []

    def fake_create_authenticated_client(
        _username: str,
        _password: str,
        _proxy: str | None = None,
        _totp_secret: str | None = None,
        verify_session: bool = False,
        **_kwargs,
    ):
        captured.append(verify_session)
        return FakeClient()

    monkeypatch.setenv("ACCOUNT_VERIFY_SESSION_ON_RESTORE", "true")
    monkeypatch.setattr(
        account_auth_runtime, "create_authenticated_client", fake_create_authenticated_client
    )

    result = services.login_account("alice", "secret", "http://proxy:8080")

    assert result["status"] == "active"
    assert captured == [True]


def test_login_account_keeps_verify_session_policy_disabled_by_default(monkeypatch):
    captured: list[bool] = []

    def fake_create_authenticated_client(
        _username: str,
        _password: str,
        _proxy: str | None = None,
        _totp_secret: str | None = None,
        verify_session: bool = False,
        **_kwargs,
    ):
        captured.append(verify_session)
        return FakeClient()

    monkeypatch.delenv("ACCOUNT_VERIFY_SESSION_ON_RESTORE", raising=False)
    monkeypatch.setattr(
        account_auth_runtime, "create_authenticated_client", fake_create_authenticated_client
    )

    result = services.login_account("alice", "secret", "http://proxy:8080")

    assert result["status"] == "active"
    assert captured == [False]


def test_import_session_archive_creates_idle_accounts_and_files():
    results = services.import_session_archive(
        {
            "alice": {"device": "ios"},
            "bob": {"device": "android"},
        }
    )

    assert {item["username"] for item in results} == {"alice", "bob"}
    assert all(item["status"] == "idle" for item in results)
    assert json.loads((services.SESSIONS_DIR / "alice.json").read_text()) == {"device": "ios"}
    assert json.loads((services.SESSIONS_DIR / "bob.json").read_text()) == {"device": "android"}


def test_bulk_set_proxy_updates_clients_and_reports_missing_accounts():
    client = FakeClient()
    state.set_account("acct-1", {"username": "alice", "proxy": None})
    state.set_client("acct-1", client)

    results = services.bulk_set_proxy(["acct-1", "missing"], "socks5://127.0.0.1:9000")

    assert results == [
        {
            "id": "acct-1",
            "username": "alice",
            "status": "ok",
            "proxy": "socks5://127.0.0.1:9000",
        },
        {
            "id": "missing",
            "status": "not_found",
        },
    ]
    assert (state.get_account("acct-1") or {})["proxy"] == "socks5://127.0.0.1:9000"
    assert client.proxy == "socks5://127.0.0.1:9000"


def test_set_account_proxy_updates_single_account_client_and_status():
    client = FakeClient()
    state.set_account("acct-1", {"username": "alice", "proxy": None})
    state.set_client("acct-1", client)
    state.set_account_status("acct-1", "active")

    result = services.set_account_proxy("acct-1", "http://proxy:8080")

    assert result["username"] == "alice"
    assert result["status"] == "active"
    assert result["proxy"] == "http://proxy:8080"
    assert (state.get_account("acct-1") or {})["proxy"] == "http://proxy:8080"
    assert client.proxy == "http://proxy:8080"


def test_read_log_entries_filters_and_orders_latest_first():
    state.log_event("1", "alice", "login_success", status="active")
    state.log_event("2", "bob", "logout", status="removed")
    state.log_event("3", "alice", "logout", status="removed")

    filtered = services.read_log_entries(username="alice", event="logout")

    assert filtered["total"] == 1
    assert filtered["entries"][0]["account_id"] == "3"
    assert filtered["entries"][0]["event"] == "logout"

    all_entries = services.read_log_entries(limit=2, offset=0)
    assert len(all_entries["entries"]) == 2
    assert all_entries["entries"][0]["account_id"] == "3"
    assert all_entries["entries"][1]["account_id"] == "2"


def test_create_scheduled_post_draft_tracks_targets_and_missing_accounts():
    state.set_account("acct-1", {"username": "alice"})
    state.set_account("acct-2", {"username": "bob"})

    result = services.create_scheduled_post_draft(
        usernames=["@alice", "charlie", "bob"],
        caption="Launch post",
        scheduled_at="2026-03-26T15:00:00Z",
    )

    assert result["success"] is True
    assert result["status"] == "scheduled"
    assert result["targets"] == ["alice", "bob"]
    assert result["not_found"] == ["charlie"]

    job = state.get_job(result["jobId"])
    assert job["caption"] == "Launch post"
    assert job["status"] == "scheduled"
    assert [item["accountId"] for item in job["targets"]] == ["acct-1", "acct-2"]


def test_relogin_account_with_tracking_marks_error_and_logs_failure(monkeypatch):
    state.set_account("acct-1", {"username": "alice", "password": "secret"})

    def fail_relogin(_account_id: str):
        raise RuntimeError("boom")

    monkeypatch.setattr(services, "relogin_account_sync", fail_relogin)

    with pytest.raises(RuntimeError, match="boom"):
        services.relogin_account_with_tracking("acct-1")

    assert state.get_account_status_value("acct-1") == "error"
    entries = services.read_log_entries(event="relogin_failed")
    assert entries["total"] == 1
    assert entries["entries"][0]["username"] == "alice"
    # detail is the translated user_message from the exception catalog, not the raw message
    assert entries["entries"][0]["detail"] == "An unexpected error occurred. Please try again."


def test_relogin_account_with_tracking_enables_verify_session_policy(monkeypatch):
    captured: list[bool] = []
    state.set_account("acct-1", {"username": "alice", "password": "secret"})

    def relogin_with_verify(
        _account_id: str,
        *,
        username: str,
        password: str,
        proxy: str | None = None,
        totp_secret: str | None = None,
        verify_session: bool = False,
        **_kwargs,
    ):
        del username, password, proxy, totp_secret
        captured.append(verify_session)
        return {"id": _account_id, "status": "active"}

    monkeypatch.setenv("ACCOUNT_VERIFY_SESSION_ON_RESTORE", "true")
    monkeypatch.setattr(services, "relogin_account_sync", relogin_with_verify)

    result = services.relogin_account_with_tracking("acct-1")

    assert result["status"] == "active"
    assert captured == [True]


def test_relogin_account_with_tracking_keeps_verify_session_policy_disabled(monkeypatch):
    captured: list[bool] = []
    state.set_account("acct-1", {"username": "alice", "password": "secret"})

    def relogin_with_verify(
        _account_id: str,
        *,
        username: str,
        password: str,
        proxy: str | None = None,
        totp_secret: str | None = None,
        verify_session: bool = False,
        **_kwargs,
    ):
        del username, password, proxy, totp_secret
        captured.append(verify_session)
        return {"id": _account_id, "status": "active"}

    monkeypatch.delenv("ACCOUNT_VERIFY_SESSION_ON_RESTORE", raising=False)
    monkeypatch.setattr(services, "relogin_account_sync", relogin_with_verify)

    result = services.relogin_account_with_tracking("acct-1")

    assert result["status"] == "active"
    assert captured == [False]


def test_bulk_relogin_accounts_uses_account_id_when_username_missing(monkeypatch):
    def fail_relogin(_account_id: str):
        raise RuntimeError("boom")

    monkeypatch.setattr(services, "relogin_account_sync", fail_relogin)

    results = asyncio.run(services.bulk_relogin_accounts(["missing"], concurrency=1))

    assert results == [
        {
            "id": "missing",
            "username": "missing",
            "status": "error",
            "error": "An unexpected error occurred. Please try again.",
            "errorCode": "unknown_instagram_error",
        }
    ]
