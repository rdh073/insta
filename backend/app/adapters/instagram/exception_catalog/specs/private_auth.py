"""Failure specs for private authentication."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_PRIVATE_ERROR = FailureSpec(
    code="private_error",
    family="private_auth",
    retryable=False,
    requires_user_action=False,
    user_message="Private account error.",
    http_hint=400,
)

SPEC_FEEDBACK_REQUIRED = FailureSpec(
    code="feedback_required",
    family="private_auth",
    retryable=True,
    requires_user_action=False,
    user_message="Action blocked temporarily. Please try later.",
    http_hint=429,
)

SPEC_PRE_LOGIN_REQUIRED = FailureSpec(
    code="pre_login_required",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="Please log in to continue.",
    http_hint=401,
)

SPEC_BAD_PASSWORD = FailureSpec(
    code="bad_password",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="Invalid password. Please check and try again.",
    http_hint=401,
)

SPEC_TWO_FACTOR_REQUIRED = FailureSpec(
    code="two_factor_required",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="Two-factor authentication required.",
    http_hint=409,
)

SPEC_BAD_CREDENTIALS = FailureSpec(
    code="bad_credentials",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="Invalid username or password.",
    http_hint=401,
)

SPEC_IS_REGULATED_C18_ERROR = FailureSpec(
    code="c18_account",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="This account is restricted due to age regulations.",
    http_hint=403,
)
