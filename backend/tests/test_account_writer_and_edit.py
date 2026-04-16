"""Tests for the InstagramAccountWriter port, AccountEditUseCases, the new
account-edit HTTP routes, and the AI tool policy classifications.

Covers:
1. Port/adapter happy-path: each method invokes the right vendor call exactly
   once with the expected kwargs.
2. Exception translation: a vendor PrivateError on set_private propagates as
   InstagramFailure via translate_instagram_error; the router surfaces the
   translated http_hint (not 500).
3. Validation: biography > 150 chars raises ValueError at the use-case layer
   *before* touching the vendor; HTTP router returns 400.
4. Policy classification: the three new tools are WRITE_SENSITIVE; unknown
   tools still default to BLOCKED (regression guard).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from instagrapi.exceptions import PrivateError

from app.adapters.instagram.account_writer import InstagramAccountWriterAdapter
from app.adapters.http.dependencies import get_account_edit_usecases
from app.application.dto.instagram_account_dto import AccountProfile
from app.application.use_cases.account.edit import AccountEditUseCases
from app.main import app

from ai_copilot.application.operator_copilot_policy import (
    ToolPolicy,
    ToolPolicyRegistry,
)


# ── Test doubles ─────────────────────────────────────────────────────────────


def _vendor_account(**overrides):
    """Build a minimal vendor-shaped Account stub for adapter tests."""
    base = {
        "pk": 42,
        "username": "operator",
        "full_name": "Op Erator",
        "biography": "hello world",
        "external_url": "https://example.com",
        "profile_pic_url": "https://cdn/pic.jpg",
        "is_private": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _RecordingClient:
    """Vendor-client stub that records every method call made against it."""

    def __init__(self, account_overrides: dict | None = None):
        self.calls: list[tuple[str, tuple, dict]] = []
        self._account_overrides = dict(account_overrides or {})

    def _record(self, name: str, args: tuple, kwargs: dict):
        self.calls.append((name, args, kwargs))

    def __getattr__(self, name: str):
        if name == "account_info":
            def _info(*args, **kwargs):
                self._record("account_info", args, kwargs)
                return _vendor_account(**self._account_overrides)
            return _info

        if name == "account_edit":
            def _edit(*args, **kwargs):
                self._record("account_edit", args, kwargs)
                merged = dict(self._account_overrides)
                merged.update(kwargs)
                return _vendor_account(**merged)
            return _edit

        def _capture(*args, **kwargs):
            self._record(name, args, kwargs)
            return True

        return _capture


class _StubClientRepo:
    def __init__(self, client):
        self._client = client

    def get(self, account_id: str):
        return self._client

    def exists(self, account_id: str) -> bool:
        return self._client is not None


class _StubAccountRepo:
    def __init__(self, account_id: str = "acc-1"):
        self._account_id = account_id

    def get(self, account_id: str):
        if account_id == self._account_id:
            return {"id": account_id, "username": "operator"}
        return None


# ── Adapter happy-path tests ─────────────────────────────────────────────────


def test_adapter_set_private_invokes_vendor_set_account_private_once():
    client = _RecordingClient(account_overrides={"is_private": True})
    adapter = InstagramAccountWriterAdapter(_StubClientRepo(client))

    profile = adapter.set_private("acc-1")

    set_calls = [c for c in client.calls if c[0] == "set_account_private"]
    info_calls = [c for c in client.calls if c[0] == "account_info"]
    assert len(set_calls) == 1
    assert set_calls[0] == ("set_account_private", (), {})
    assert len(info_calls) == 1
    assert isinstance(profile, AccountProfile)
    assert profile.is_private is True


def test_adapter_set_public_invokes_vendor_set_account_public_once():
    client = _RecordingClient(account_overrides={"is_private": False})
    adapter = InstagramAccountWriterAdapter(_StubClientRepo(client))

    profile = adapter.set_public("acc-1")

    set_calls = [c for c in client.calls if c[0] == "set_account_public"]
    assert len(set_calls) == 1
    assert set_calls[0] == ("set_account_public", (), {})
    assert profile.is_private is False


def test_adapter_change_avatar_invokes_change_profile_picture_once():
    client = _RecordingClient()
    adapter = InstagramAccountWriterAdapter(_StubClientRepo(client))

    adapter.change_avatar("acc-1", "/tmp/pic.jpg")

    change_calls = [c for c in client.calls if c[0] == "change_profile_picture"]
    assert len(change_calls) == 1
    assert change_calls[0] == ("change_profile_picture", ("/tmp/pic.jpg",), {})


def test_adapter_edit_profile_passes_only_provided_fields():
    client = _RecordingClient()
    adapter = InstagramAccountWriterAdapter(_StubClientRepo(client))

    adapter.edit_profile("acc-1", first_name="New Name", biography="bio")

    edit_calls = [c for c in client.calls if c[0] == "account_edit"]
    assert len(edit_calls) == 1
    _, _, kwargs = edit_calls[0]
    assert kwargs == {"first_name": "New Name", "biography": "bio"}
    assert "external_url" not in kwargs


def test_adapter_set_presence_disabled_invokes_set_presence_status_once():
    client = _RecordingClient()
    adapter = InstagramAccountWriterAdapter(_StubClientRepo(client))

    profile = adapter.set_presence_disabled("acc-1", True)

    presence_calls = [c for c in client.calls if c[0] == "set_presence_status"]
    assert len(presence_calls) == 1
    assert presence_calls[0] == ("set_presence_status", (True,), {})
    assert profile.presence_disabled is True


# ── Exception translation ────────────────────────────────────────────────────


class _RaisingClient:
    """Vendor-client stub that raises on the configured method, otherwise
    forwards to a recording stub. The first set_account_private call raises."""

    def __init__(self, error: Exception):
        self._error = error

    def set_account_private(self):
        raise self._error

    def __getattr__(self, name: str):
        def _capture(*_args, **_kwargs):
            return True

        return _capture


def test_adapter_private_error_propagates_translated_failure_not_raw_string():
    raw = "RAW_VENDOR_PRIVATE_ERROR_DO_NOT_LEAK"
    adapter = InstagramAccountWriterAdapter(
        _StubClientRepo(_RaisingClient(PrivateError(raw)))
    )

    with pytest.raises(ValueError) as excinfo:
        adapter.set_private("acc-1")

    failure = getattr(excinfo.value, "_instagram_failure", None)
    assert failure is not None, "translated InstagramFailure must be attached"
    assert failure.code == "private_error"
    assert raw not in str(excinfo.value)


def test_router_surfaces_translated_http_hint_not_500_for_private_error():
    """End-to-end: PrivateError on /privacy returns the translated http_hint
    (NOT 500). The HTTP status is whatever the failure catalog dictates for
    PrivateError — what matters is that it is NOT the unhandled-exception 500.
    """

    class _FailingUseCases:
        def set_private(self, account_id: str):
            err = PrivateError("blocked")
            from app.adapters.instagram.error_utils import (
                attach_instagram_failure,
                translate_instagram_error,
            )

            failure = translate_instagram_error(
                err, operation="set_account_private", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure)

    app.dependency_overrides[get_account_edit_usecases] = lambda: _FailingUseCases()
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/accounts/acc-1/privacy", json={"private": True}
            )
    finally:
        app.dependency_overrides.pop(get_account_edit_usecases, None)

    assert resp.status_code != 500
    body = resp.json()
    detail = body.get("detail", {})
    assert isinstance(detail, dict)
    assert detail.get("code") == "private_error"


# ── Validation (use-case + router) ───────────────────────────────────────────


def test_use_case_rejects_biography_over_150_chars_before_vendor_call():
    """biography > 150 chars must raise ValueError without touching the writer."""

    class _SpyWriter:
        def __init__(self):
            self.called = False

        def edit_profile(self, *_args, **_kwargs):
            self.called = True
            raise AssertionError("vendor must not be called when validation fails")

        # Other port methods unused in this test.
        def set_private(self, *_a, **_kw): ...
        def set_public(self, *_a, **_kw): ...
        def change_avatar(self, *_a, **_kw): ...
        def set_presence_disabled(self, *_a, **_kw): ...

    writer = _SpyWriter()
    usecases = AccountEditUseCases(
        account_repo=_StubAccountRepo(),
        client_repo=_StubClientRepo(client=object()),
        account_writer=writer,
    )

    with pytest.raises(ValueError) as excinfo:
        usecases.edit_profile("acc-1", biography="x" * 200)

    assert "biography" in str(excinfo.value).lower()
    assert writer.called is False


def test_router_returns_400_for_biography_over_150_chars():
    class _ValidationStubUseCases:
        def edit_profile(self, *_args, **_kwargs):
            raise ValueError("biography exceeds 150 characters (got 200)")

    app.dependency_overrides[get_account_edit_usecases] = lambda: _ValidationStubUseCases()
    try:
        with TestClient(app) as client:
            resp = client.patch(
                "/api/accounts/acc-1/profile", json={"biography": "x" * 200}
            )
    finally:
        app.dependency_overrides.pop(get_account_edit_usecases, None)

    assert resp.status_code == 400


# ── Privacy round-trip via mocked use cases ──────────────────────────────────


def test_router_privacy_round_trip_through_mocked_usecases():
    """{"private": true} → is_private=true, then {"private": false} → is_private=false."""

    state = {"private": False}

    class _StateUseCases:
        def set_private(self, account_id: str):
            state["private"] = True
            return AccountProfile(id=42, username="operator", is_private=True)

        def set_public(self, account_id: str):
            state["private"] = False
            return AccountProfile(id=42, username="operator", is_private=False)

    app.dependency_overrides[get_account_edit_usecases] = lambda: _StateUseCases()
    try:
        with TestClient(app) as client:
            r1 = client.post("/api/accounts/acc-1/privacy", json={"private": True})
            r2 = client.post("/api/accounts/acc-1/privacy", json={"private": False})
    finally:
        app.dependency_overrides.pop(get_account_edit_usecases, None)

    assert r1.status_code == 200 and r1.json()["isPrivate"] is True
    assert r2.status_code == 200 and r2.json()["isPrivate"] is False


# ── Policy classification regression guard ───────────────────────────────────


def test_new_account_edit_tools_are_write_sensitive():
    registry = ToolPolicyRegistry()
    for tool in ("set_account_privacy", "edit_account_profile", "set_account_presence"):
        cls = registry.classify(tool)
        assert cls.policy is ToolPolicy.WRITE_SENSITIVE, (
            f"{tool} must be WRITE_SENSITIVE, got {cls.policy}"
        )
        assert cls.requires_approval is True, (
            f"{tool} must require operator approval"
        )


def test_unknown_tool_still_defaults_to_blocked():
    cls = ToolPolicyRegistry().classify("definitely_not_a_real_tool_name_xyz")
    assert cls.policy is ToolPolicy.BLOCKED
    assert cls.requires_approval is False


def test_change_avatar_is_not_exposed_as_an_ai_tool():
    """change_avatar is intentionally excluded from the LLM-callable surface
    (documented in coverage_exceptions.json). The HTTP route remains."""
    from app.adapters.ai.tool_registry.builder import (
        list_registered_tool_names_for_policy_audit,
    )

    names = set(list_registered_tool_names_for_policy_audit())
    assert "change_avatar" not in names
    assert "set_account_avatar" not in names
