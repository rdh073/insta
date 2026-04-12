"""Failure specs for account."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_ACCOUNT_SUSPENDED = FailureSpec(
    code="account_suspended",
    family="account",
    retryable=False,
    requires_user_action=False,
    user_message="Your account has been suspended.",
    http_hint=403,
)

SPEC_TERMS_UNBLOCK = FailureSpec(
    code="terms_violation",
    family="account",
    retryable=False,
    requires_user_action=True,
    user_message="Account blocked due to terms violation.",
    http_hint=403,
)

SPEC_TERMS_ACCEPT = FailureSpec(
    code="terms_accept_required",
    family="account",
    retryable=False,
    requires_user_action=True,
    user_message="Please accept updated terms.",
    http_hint=409,
)

SPEC_ABOUT_US_ERROR = FailureSpec(
    code="about_us_error",
    family="account",
    retryable=False,
    requires_user_action=False,
    user_message="Account error.",
    http_hint=400,
)

SPEC_RESET_PASSWORD_ERROR = FailureSpec(
    code="password_reset_failed",
    family="account",
    retryable=True,
    requires_user_action=False,
    user_message="Password reset failed. Try again.",
    http_hint=400,
)

SPEC_UNSUPPORTED_ERROR = FailureSpec(
    code="unsupported_operation",
    family="account",
    retryable=False,
    requires_user_action=False,
    user_message="This operation is not supported.",
    http_hint=400,
)

SPEC_UNSUPPORTED_SETTING_VALUE = FailureSpec(
    code="unsupported_setting",
    family="account",
    retryable=False,
    requires_user_action=False,
    user_message="This setting value is not supported.",
    http_hint=400,
)
