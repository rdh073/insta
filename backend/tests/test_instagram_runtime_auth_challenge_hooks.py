"""Regression tests for non-interactive challenge handling in runtime auth."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from instagram_runtime import auth
from state import CaptchaChallengeRequired, ChallengeRequired, LoginRequired


class _StubClient:
    def __init__(self) -> None:
        self.proxy = None
        self.device = None
        self.user_agent = None
        self.country = None
        self.country_code = None
        self.locale = None
        self.timezone_offset = None

    def set_proxy(self, proxy: str) -> None:
        self.proxy = proxy

    def set_device(self, device: dict) -> None:
        self.device = device

    def set_user_agent(self, user_agent: str) -> None:
        self.user_agent = user_agent

    def set_country(self, country: str) -> None:
        self.country = country

    def set_country_code(self, country_code: int) -> None:
        self.country_code = country_code

    def set_locale(self, locale: str) -> None:
        self.locale = locale

    def set_timezone_offset(self, timezone_offset: int) -> None:
        self.timezone_offset = timezone_offset


def test_new_client_installs_non_interactive_challenge_handlers(monkeypatch: pytest.MonkeyPatch):
    def _fail_input(*_args, **_kwargs):
        raise AssertionError("stdin input must never be used in backend challenge flow")

    monkeypatch.setattr("builtins.input", _fail_input)

    client = auth.new_client(
        proxy="http://proxy:8080",
        ig_client_cls=_StubClient,
        device_profile_factory=lambda: ({}, "ua"),
    )

    assert callable(client.handle_exception)
    assert callable(client.challenge_code_handler)
    assert callable(client.change_password_handler)

    with pytest.raises(ChallengeRequired):
        client.handle_exception(client, ChallengeRequired("challenge"))
    with pytest.raises(ChallengeRequired):
        client.challenge_code_handler("alice", "EMAIL")
    with pytest.raises(ChallengeRequired):
        client.change_password_handler("alice")


def test_new_client_applies_explicit_geo_locale_settings():
    client = auth.new_client(
        proxy=None,
        country="US",
        country_code=1,
        locale="en_US",
        timezone_offset=-18000,
        ig_client_cls=_StubClient,
        device_profile_factory=lambda: ({}, "ua"),
    )

    assert client.country == "US"
    assert client.country_code == 1
    assert client.locale == "en_US"
    assert client.timezone_offset == -18000


def test_new_client_uses_indonesia_defaults_when_unset():
    client = auth.new_client(
        proxy=None,
        ig_client_cls=_StubClient,
        device_profile_factory=lambda: ({}, "ua"),
    )

    assert client.country == "ID"
    assert client.country_code == 62
    assert client.locale == "id_ID"
    assert client.timezone_offset == 25200


def test_new_client_env_overrides_default_geo_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("INSTAGRAM_COUNTRY", "JP")
    monkeypatch.setenv("INSTAGRAM_COUNTRY_CODE", "81")
    monkeypatch.setenv("INSTAGRAM_LOCALE", "ja_JP")
    monkeypatch.setenv("INSTAGRAM_TIMEZONE_OFFSET", "32400")

    client = auth.new_client(
        proxy=None,
        ig_client_cls=_StubClient,
        device_profile_factory=lambda: ({}, "ua"),
    )

    assert client.country == "JP"
    assert client.country_code == 81
    assert client.locale == "ja_JP"
    assert client.timezone_offset == 32400


def test_create_authenticated_client_propagates_captcha_challenge_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(auth, "SESSIONS_DIR", tmp_path)

    session_file = tmp_path / "alice.json"
    session_file.write_text(json.dumps({"uuids": {"phone_id": "p"}}))

    class _CaptchaClient(_StubClient):
        def __init__(self) -> None:
            super().__init__()
            self.login_calls = 0

        def load_settings(self, _path: Path) -> None:
            pass

        def get_settings(self) -> dict:
            return {"uuids": {"phone_id": "p"}}

        def login(self, *_args, **_kwargs) -> None:
            self.login_calls += 1
            raise CaptchaChallengeRequired("captcha required")

        def dump_settings(self, _path: Path) -> None:
            raise AssertionError("dump_settings must not be called on challenge")

    client = _CaptchaClient()

    with pytest.raises(CaptchaChallengeRequired):
        auth.create_authenticated_client(
            "alice",
            "secret",
            proxy=None,
            totp_secret=None,
            new_client_fn=lambda _proxy: client,
        )

    # Session restore should fail fast on challenge without extra fallback login attempts.
    assert client.login_calls == 1


def test_create_authenticated_client_verify_session_falls_back_to_reauth_on_invalid_restore(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(auth, "SESSIONS_DIR", tmp_path)

    session_file = tmp_path / "alice.json"
    session_file.write_text(json.dumps({"uuids": {"phone_id": "p"}}))

    class _VerifyFallbackClient(_StubClient):
        def __init__(self) -> None:
            super().__init__()
            self.login_calls: list[dict] = []
            self.dumped = 0

        def load_settings(self, _path: Path) -> None:
            pass

        def get_settings(self) -> dict:
            return {"uuids": {"phone_id": "p"}}

        def set_settings(self, _settings: dict) -> None:
            pass

        def set_uuids(self, _uuids: dict) -> None:
            pass

        def login(self, username: str, password: str, **kwargs) -> None:
            self.login_calls.append({"username": username, "password": password, **kwargs})
            if kwargs.get("verification_code"):
                return
            return

        def account_info(self):
            raise LoginRequired("expired after restore")

        def dump_settings(self, _path: Path) -> None:
            self.dumped += 1

    client = _VerifyFallbackClient()

    result = auth.create_authenticated_client(
        "alice",
        "secret",
        proxy=None,
        verify_session=True,
        new_client_fn=lambda _proxy: client,
    )

    assert result is client
    # First call restores session; second call is forced fresh credential login.
    assert len(client.login_calls) == 2
    assert client.login_calls[0].get("verification_code") is None
    assert client.login_calls[1].get("verification_code", None) == ""
    assert client.dumped == 1


def test_create_authenticated_client_fresh_fallback_restores_full_device_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Regression for device-drift on fresh-login fallback.

    When the session-restore path raises a non-terminal Exception and
    create_authenticated_client falls through to the fresh-login branch, the
    new client must keep the saved device_settings, user_agent, AND uuids
    from the session file — not just uuids.

    Before the fix, only uuids were carried over. Each _new_client_with_optional_geo
    call picks a random device_profile_factory(), so the fresh-login branch
    would post accounts/login/ with a *different* user_agent every time.
    Instagram's anti-abuse sees one account logging in from many devices in
    minutes, returns bad_password decoys, and eventually locks the account
    into ChallengeRequired. Root-caused live 2026-04-17 on doloresball269.
    """

    monkeypatch.setattr(auth, "SESSIONS_DIR", tmp_path)

    saved_device = {"manufacturer": "Samsung", "model": "SM-A325F", "android_version": 30}
    saved_user_agent = "Instagram 364.0.0.35.86 Android (30/11; 400dpi; 1080x2400; Samsung; SM-A325F; a32; mt6853; en_US; 374010953)"
    saved_uuids = {"phone_id": "PHONE-UUID-FIXED", "android_device_id": "android-UUID-FIXED"}

    session_file = tmp_path / "alice.json"
    session_file.write_text(
        json.dumps(
            {
                "uuids": saved_uuids,
                "device_settings": saved_device,
                "user_agent": saved_user_agent,
                "authorization_data": {"sessionid": "stale"},
            }
        )
    )

    # Tracks both clients: the session-restore client and the fresh-fallback client.
    # We assert on the second one.
    created_clients: list["_FallbackClient"] = []

    class _FallbackClient(_StubClient):
        def __init__(self) -> None:
            super().__init__()
            self.loaded_settings = False
            self.set_uuids_called_with: dict | None = None
            self.set_device_called_with: dict | None = None
            self.set_user_agent_called_with: str | None = None
            self.login_calls: list[dict] = []
            self.dumped = False
            created_clients.append(self)

        def load_settings(self, _path: Path) -> None:
            self.loaded_settings = True

        def get_settings(self) -> dict:
            # Returned from the FIRST client right after load_settings so the
            # outer flow captures the saved fingerprint to replay on the fallback.
            return {
                "uuids": saved_uuids,
                "device_settings": saved_device,
                "user_agent": saved_user_agent,
            }

        def set_uuids(self, uuids: dict) -> None:
            self.set_uuids_called_with = uuids

        def set_device(self, device: dict) -> None:
            super().set_device(device)
            self.set_device_called_with = device

        def set_user_agent(self, user_agent: str) -> None:
            super().set_user_agent(user_agent)
            self.set_user_agent_called_with = user_agent

        def login(self, username: str, password: str, **kwargs) -> None:
            self.login_calls.append({"username": username, "password": password, **kwargs})
            if self.loaded_settings and len(self.login_calls) == 1:
                # First client: session restore — simulate a transient error
                # that is NOT BadPassword, ChallengeRequired, or LoginRequired.
                # Per existing auth.py:412-415 this falls through to fresh login.
                raise RuntimeError("transient network blip")

        def dump_settings(self, _path: Path) -> None:
            self.dumped = True

    # Use a different client per _new_client_with_optional_geo call so the test
    # can assert the fresh-fallback client (second created) got the device restored.
    client_factory_calls = {"count": 0}

    def _new_client_fn(_proxy):
        client_factory_calls["count"] += 1
        return _FallbackClient()

    auth.create_authenticated_client(
        "alice",
        "secret",
        proxy=None,
        new_client_fn=_new_client_fn,
    )

    # Two clients were created: restore path + fresh-fallback path.
    assert client_factory_calls["count"] == 2
    assert len(created_clients) == 2

    fallback_client = created_clients[1]

    # The fallback client MUST have been configured with the saved device.
    assert fallback_client.set_device_called_with == saved_device, (
        "fresh-login fallback dropped the saved device_settings — "
        "this is what caused Instagram to see each relogin as a new device"
    )
    assert fallback_client.set_user_agent_called_with == saved_user_agent, (
        "fresh-login fallback dropped the saved user_agent"
    )
    assert fallback_client.set_uuids_called_with == saved_uuids, (
        "fresh-login fallback dropped the saved UUIDs"
    )

    # And it must have posted the credentials login (expected behaviour).
    assert len(fallback_client.login_calls) == 1
