"""Regression tests for non-interactive challenge handling in runtime auth."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from instagram_runtime import auth
from state import CaptchaChallengeRequired, ChallengeRequired


class _StubClient:
    def __init__(self) -> None:
        self.proxy = None
        self.device = None
        self.user_agent = None

    def set_proxy(self, proxy: str) -> None:
        self.proxy = proxy

    def set_device(self, device: dict) -> None:
        self.device = device

    def set_user_agent(self, user_agent: str) -> None:
        self.user_agent = user_agent


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

