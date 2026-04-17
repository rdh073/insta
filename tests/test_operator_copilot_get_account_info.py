"""End-to-end tests for the get_account_info tool handler.

Regression guard for the followers: null bug (F1 in copilot-multi-provider-
live-debug-2026-04-17 audit closure).  Verifies that the tool registry handler
surfaces a real integer in the `followers` field instead of null.

Coverage:
1. Handler returns non-null followers when use case returns real count.
2. Handler returns non-null following / mediaCount.
3. A zero follower count maps to 0 (int), not None/null.
4. Errors from the use case are forwarded as {"error": ...}.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.adapters.ai.tool_registry.account_tools import register_account_tools
from app.adapters.ai.tool_registry.builder import ToolBuilderContext
from app.application.dto.account_dto import AccountInfoResponse


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _execute_get_account_info(
    response: AccountInfoResponse,
    username: str = "doloresball269",
) -> dict:
    """Wire the handler through a real ToolBuilderContext with mocked use cases."""
    profile_usecases = MagicMock()
    profile_usecases.find_by_username.return_value = "acc-001"
    profile_usecases.get_account_info.return_value = response

    context = ToolBuilderContext(
        account_usecases=MagicMock(),
        postjob_usecases=MagicMock(),
        account_profile_usecases=profile_usecases,
    )

    captured: dict = {}

    class _CapturingRegistry:
        def register(self, name, handler, schema):
            captured[name] = handler

    register_account_tools(_CapturingRegistry(), context)  # type: ignore[arg-type]
    return captured["get_account_info"]({"username": username})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetAccountInfoToolFollowers:
    def test_followers_is_non_null_integer(self):
        response = AccountInfoResponse(
            username="doloresball269",
            followers=4200,
            following=310,
            media_count=87,
        )
        result = _execute_get_account_info(response)

        assert result.get("followers") == 4200
        assert result.get("followers") is not None

    def test_following_is_non_null_integer(self):
        response = AccountInfoResponse(
            username="doloresball269",
            followers=4200,
            following=310,
            media_count=87,
        )
        result = _execute_get_account_info(response)

        assert result.get("following") == 310

    def test_media_count_is_non_null_integer(self):
        response = AccountInfoResponse(
            username="doloresball269",
            followers=4200,
            following=310,
            media_count=87,
        )
        result = _execute_get_account_info(response)

        assert result.get("mediaCount") == 87

    def test_zero_followers_is_integer_not_null(self):
        """A brand-new account with 0 followers must return 0, not None."""
        response = AccountInfoResponse(
            username="newaccount",
            followers=0,
            following=0,
            media_count=0,
        )
        result = _execute_get_account_info(response, username="newaccount")

        assert result.get("followers") == 0
        assert result.get("followers") is not None

    def test_error_from_use_case_is_forwarded(self):
        response = AccountInfoResponse(
            username="brokenaccount",
            error="Account not logged in",
        )
        result = _execute_get_account_info(response, username="brokenaccount")

        assert "error" in result
        assert "followers" not in result

    def test_result_contains_username(self):
        response = AccountInfoResponse(
            username="doloresball269",
            followers=4200,
            following=310,
            media_count=87,
            biography="Test bio",
            is_private=False,
            is_verified=False,
            is_business=False,
        )
        result = _execute_get_account_info(response)

        assert result.get("username") == "doloresball269"

    def test_biography_is_included(self):
        response = AccountInfoResponse(
            username="doloresball269",
            followers=4200,
            following=310,
            media_count=87,
            biography="Living life",
        )
        result = _execute_get_account_info(response)

        assert result.get("biography") == "Living life"


# ---------------------------------------------------------------------------
# PII guard — regression tests for LLM boundary protection
# ---------------------------------------------------------------------------

_FORBIDDEN_PII_KEYS = frozenset({
    "birthday",
    "phone_number",
    "national_number",
    "email",
    "supervision_info",
    "interop_messaging_user_fbid",
    "pk_id",
    "fbid_v2",
})

_ALLOWED_RESULT_KEYS = frozenset({
    "username",
    "fullName",
    "biography",
    "followers",
    "following",
    "mediaCount",
    "isPrivate",
    "isVerified",
    "isBusiness",
})


def _all_keys(obj, _path="") -> set[str]:
    """Recursively collect all dict keys in a nested structure."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _all_keys(v, f"{_path}.{k}")
    elif isinstance(obj, list):
        for item in obj:
            keys |= _all_keys(item, _path)
    return keys


class TestGetAccountInfoToolPIIGuard:
    """Regression guard: tool result must never contain PII keys.

    These tests assert that even if the underlying DTO or use case were to
    add PII fields in the future, the tool handler's explicit field listing
    keeps them out of the LLM-bound tool result.
    """

    def test_successful_result_contains_no_forbidden_pii_keys(self):
        response = AccountInfoResponse(
            username="testuser",
            full_name="Test User",
            biography="Bio",
            followers=1000,
            following=500,
            media_count=42,
            is_private=False,
            is_verified=True,
            is_business=False,
        )
        result = _execute_get_account_info(response)

        all_keys = _all_keys(result)
        violations = all_keys & _FORBIDDEN_PII_KEYS
        assert not violations, (
            f"PII keys found in get_account_info tool result: {violations!r}"
        )

    def test_error_result_contains_no_forbidden_pii_keys(self):
        response = AccountInfoResponse(
            username="testuser",
            error="Account not logged in",
        )
        result = _execute_get_account_info(response)

        all_keys = _all_keys(result)
        violations = all_keys & _FORBIDDEN_PII_KEYS
        assert not violations, (
            f"PII keys found in error tool result: {violations!r}"
        )

    def test_successful_result_contains_only_allowed_keys(self):
        """Whitelist check: result keys must be a subset of the declared safe set."""
        response = AccountInfoResponse(
            username="testuser",
            full_name="Test User",
            biography="Bio",
            followers=1000,
            following=500,
            media_count=42,
            is_private=False,
            is_verified=True,
            is_business=False,
        )
        result = _execute_get_account_info(response)

        unexpected = set(result.keys()) - _ALLOWED_RESULT_KEYS
        assert not unexpected, (
            f"Unexpected keys in get_account_info tool result: {unexpected!r}"
        )
