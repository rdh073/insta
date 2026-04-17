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


def test_create_authenticated_client_fresh_fallback_preserves_device_uuids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Fresh-login fallback must restore the saved UUIDs so Instagram sees
    the same device across retries.

    Per instagrapi best-practices guide, UUIDs (phone_id, android_device_id,
    advertising_id, uuid, …) are the device identity Instagram actually
    checks — device_settings.model / user_agent are cosmetic for our
    purposes. See:
    https://subzeroid.github.io/instagrapi/usage-guide/best-practices.html
    """

    monkeypatch.setattr(auth, "SESSIONS_DIR", tmp_path)

    saved_uuids = {"phone_id": "PHONE-UUID-FIXED", "android_device_id": "android-UUID-FIXED"}

    session_file = tmp_path / "alice.json"
    session_file.write_text(
        json.dumps(
            {
                "uuids": saved_uuids,
                "authorization_data": {"sessionid": "stale"},
            }
        )
    )

    created_clients: list["_FallbackClient"] = []

    class _FallbackClient(_StubClient):
        def __init__(self) -> None:
            super().__init__()
            self.loaded_settings = False
            self.set_uuids_called_with: dict | None = None
            self.login_calls: list[dict] = []
            self.dumped = False
            created_clients.append(self)

        def load_settings(self, _path: Path) -> None:
            self.loaded_settings = True

        def get_settings(self) -> dict:
            return {"uuids": saved_uuids}

        def set_uuids(self, uuids: dict) -> None:
            self.set_uuids_called_with = uuids

        def login(self, username: str, password: str, **kwargs) -> None:
            self.login_calls.append({"username": username, "password": password, **kwargs})
            if self.loaded_settings and len(self.login_calls) == 1:
                # First client: session restore — simulate a transient error
                # that is NOT BadPassword, ChallengeRequired, or LoginRequired.
                # Falls through to fresh login per auth.py's Exception handler.
                raise RuntimeError("transient network blip")

        def dump_settings(self, _path: Path) -> None:
            self.dumped = True

    factory_calls = {"count": 0}

    def _new_client_fn(_proxy):
        factory_calls["count"] += 1
        return _FallbackClient()

    auth.create_authenticated_client(
        "alice",
        "secret",
        proxy=None,
        new_client_fn=_new_client_fn,
    )

    assert factory_calls["count"] == 2
    fallback_client = created_clients[1]
    assert fallback_client.set_uuids_called_with == saved_uuids
    assert len(fallback_client.login_calls) == 1
