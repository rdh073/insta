from __future__ import annotations

import json

import instagram
import pytest
import state
from app.adapters.instagram.rate_limit_guard import rate_limit_guard
from app.domain.instagram_failures import InstagramFailure
from instagram_runtime import relogin as relogin_runtime


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
        self.logged_out = False
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


def test_create_authenticated_client_retries_with_fresh_client(monkeypatch):
    created_clients: list[RetryClient] = []

    class RetryClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.should_fail = not created_clients
            created_clients.append(self)

        def login(self, username: str, password: str, **kwargs):
            super().login(username, password)
            if self.should_fail:
                raise instagram.LoginRequired()

    monkeypatch.setattr(instagram, "IGClient", RetryClient)
    (instagram.SESSIONS_DIR / "alice.json").write_text(json.dumps({"session": "stale"}))

    client = instagram.create_authenticated_client("alice", "secret", "http://proxy:8080")

    assert client is created_clients[1]
    assert len(created_clients) == 2
    assert created_clients[0].proxy == "http://proxy:8080"
    assert created_clients[1].proxy == "http://proxy:8080"
    assert (instagram.SESSIONS_DIR / "alice.json").exists()


def test_relogin_account_sync_replaces_stale_client_and_updates_state(monkeypatch):
    monkeypatch.setattr(instagram, "IGClient", FakeClient)

    stale_client = FakeClient()
    state.set_account("acct-1", {
        "username": "alice",
        "password": "secret",
        "proxy": "http://proxy:8080",
    })
    state.set_client("acct-1", stale_client)

    result = instagram.relogin_account_sync(
        "acct-1",
        username="alice",
        password="secret",
        proxy="http://proxy:8080",
    )

    # stale client reference is dropped (pop_client) but NOT logged out —
    # calling logout() would invalidate the server-side session file we reuse.
    assert stale_client.logged_out is False
    assert isinstance(state.get_client("acct-1"), FakeClient)
    assert state.get_client("acct-1") is not stale_client
    assert state.get_account_status_value("acct-1") == "active"
    # followers enrichment happens via background task, not during relogin
    assert result["status"] == "active"


def test_relogin_account_sync_threads_verify_session_to_session_restore_strategy(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: list[bool] = []

    def strategy(
        _username: str,
        _password: str,
        _proxy: str | None,
        _totp: str | None,
        verify_session: bool = False,
    ):
        captured.append(verify_session)
        return FakeClient()

    monkeypatch.setattr(relogin_runtime, "pop_client", lambda _account_id: None)
    monkeypatch.setattr(
        relogin_runtime,
        "activate_account_client",
        lambda _account_id, _client: {"id": _account_id, "status": "active"},
    )
    monkeypatch.setattr(relogin_runtime, "log_event", lambda *_args, **_kwargs: None)

    result = relogin_runtime.relogin_account_sync(
        "acct-v",
        username="alice",
        password="secret",
        verify_session=True,
        relogin_strategies={"session_restore": strategy},
    )

    assert result["status"] == "active"
    assert captured == [True]


def test_relogin_account_sync_keeps_backward_compatible_strategy_signature(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = {"count": 0}

    def legacy_strategy(
        _username: str,
        _password: str,
        _proxy: str | None,
        _totp: str | None,
    ):
        calls["count"] += 1
        return FakeClient()

    monkeypatch.setattr(relogin_runtime, "pop_client", lambda _account_id: None)
    monkeypatch.setattr(
        relogin_runtime,
        "activate_account_client",
        lambda _account_id, _client: {"id": _account_id, "status": "active"},
    )
    monkeypatch.setattr(relogin_runtime, "log_event", lambda *_args, **_kwargs: None)

    result = relogin_runtime.relogin_account_sync(
        "acct-legacy",
        username="alice",
        password="secret",
        verify_session=True,
        relogin_strategies={"session_restore": legacy_strategy},
    )

    assert result["status"] == "active"
    assert calls["count"] == 1


@pytest.mark.parametrize(
    "failure_code",
    ["rate_limit", "wait_required", "feedback_required"],
)
def test_relogin_retry_uses_jittered_cooldown_for_429_family(
    monkeypatch: pytest.MonkeyPatch,
    failure_code: str,
):
    attempts = {"count": 0}
    sleep_calls: list[float] = []

    def flaky_strategy(
        _username: str,
        _password: str,
        _proxy: str | None,
        _totp: str | None,
        _verify_session: bool = False,
    ):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("429 family transient")
        return FakeClient()

    def translate_exception(
        _error: Exception,
        *,
        operation: str,
        account_id: str | None = None,
        username: str | None = None,
    ) -> InstagramFailure:
        assert operation == "relogin"
        assert account_id == "acct-rl"
        assert username == "alice"
        return InstagramFailure(
            code=failure_code,
            family="proxy" if failure_code != "feedback_required" else "private_auth",
            retryable=True,
            requires_user_action=False,
            user_message="rate limited",
            http_hint=429,
        )

    monkeypatch.setattr(relogin_runtime, "pop_client", lambda _account_id: None)
    monkeypatch.setattr(
        relogin_runtime,
        "activate_account_client",
        lambda _account_id, _client: {"id": _account_id, "status": "active"},
    )
    monkeypatch.setattr(relogin_runtime, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(relogin_runtime, "_rate_limit_retry_after_seconds", lambda _account_id: 90.0)

    result = relogin_runtime.relogin_account_sync(
        "acct-rl",
        username="alice",
        password="secret",
        relogin_strategies={"session_restore": flaky_strategy},
        translate_exception_fn=translate_exception,
        sleep_fn=sleep_calls.append,
        jitter_uniform_fn=lambda _lo, _hi: 4.0,
    )

    assert result["status"] == "active"
    assert sleep_calls == [94.0, 94.0]
    assert sleep_calls != [1.0, 2.0]


def test_relogin_retry_keeps_standard_backoff_for_non_429_transient(
    monkeypatch: pytest.MonkeyPatch,
):
    attempts = {"count": 0}
    sleep_calls: list[float] = []

    def flaky_strategy(
        _username: str,
        _password: str,
        _proxy: str | None,
        _totp: str | None,
        _verify_session: bool = False,
    ):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("network glitch")
        return FakeClient()

    def classify_exception(
        _error: Exception,
        *,
        operation: str,
        account_id: str | None = None,
        username: str | None = None,
    ) -> InstagramFailure:
        assert operation == "relogin"
        assert account_id == "acct-net"
        assert username == "alice"
        return InstagramFailure(
            code="network_error",
            family="common_client",
            retryable=True,
            requires_user_action=False,
            user_message="Temporary network issue",
            http_hint=503,
        )

    monkeypatch.setattr(relogin_runtime, "pop_client", lambda _account_id: None)
    monkeypatch.setattr(
        relogin_runtime,
        "activate_account_client",
        lambda _account_id, _client: {"id": _account_id, "status": "active"},
    )
    monkeypatch.setattr(relogin_runtime, "log_event", lambda *_args, **_kwargs: None)

    result = relogin_runtime.relogin_account_sync(
        "acct-net",
        username="alice",
        password="secret",
        relogin_strategies={"session_restore": flaky_strategy},
        classify_exception_fn=classify_exception,
        sleep_fn=sleep_calls.append,
    )

    assert result["status"] == "active"
    assert sleep_calls == [1.0, 2.0]


def test_relogin_flow_marks_rate_limit_guard_side_effects(
    monkeypatch: pytest.MonkeyPatch,
):
    account_id = "acct-guard"
    rate_limit_guard.clear(account_id)

    def fail_strategy(
        _username: str,
        _password: str,
        _proxy: str | None,
        _totp: str | None,
        _verify_session: bool = False,
    ):
        raise RuntimeError("too many requests")

    failure = InstagramFailure(
        code="rate_limit",
        family="proxy",
        retryable=False,
        requires_user_action=False,
        user_message="Rate limited. Please wait before trying again.",
        http_hint=429,
    )

    monkeypatch.setattr(
        "app.adapters.instagram.error_utils.instagram_exception_handler.handle",
        lambda *_args, **_kwargs: failure,
    )
    monkeypatch.setattr(
        instagram,
        "_RELOGIN_STRATEGIES",
        {
            "session_restore": fail_strategy,
            "fresh_credentials": fail_strategy,
        },
    )

    with pytest.raises(RuntimeError):
        instagram.relogin_account_sync(
            account_id,
            username="alice",
            password="secret",
        )

    limited, retry_after = rate_limit_guard.is_limited(account_id)
    assert limited is True
    assert retry_after > 0
    rate_limit_guard.clear(account_id)
