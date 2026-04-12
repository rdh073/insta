"""Failure specs for user."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_USER_ERROR = FailureSpec(
    code="user_error",
    family="user",
    retryable=False,
    requires_user_action=False,
    user_message="User operation failed.",
    http_hint=400,
)

SPEC_USER_NOT_FOUND = FailureSpec(
    code="user_not_found",
    family="user",
    retryable=False,
    requires_user_action=False,
    user_message="User not found.",
    http_hint=404,
)

SPEC_PRIVATE_ACCOUNT = FailureSpec(
    code="private_account",
    family="user",
    retryable=False,
    requires_user_action=False,
    user_message="This account is private.",
    http_hint=403,
)
