"""Failure specs for common client."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_CLIENT_ERROR = FailureSpec(
    code="client_error",
    family="common_client",
    retryable=False,
    requires_user_action=False,
    user_message="An Instagram API error occurred.",
    http_hint=400,
)

SPEC_GENERIC_REQUEST_ERROR = FailureSpec(
    code="request_error",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Request failed. Please try again.",
    http_hint=500,
)

SPEC_CLIENT_GRAPHQL_ERROR = FailureSpec(
    code="graphql_error",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="GraphQL request failed. Please try again.",
    http_hint=500,
)

SPEC_CLIENT_JSON_DECODE_ERROR = FailureSpec(
    code="json_decode_error",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to process response. Please try again.",
    http_hint=500,
)

SPEC_CLIENT_CONNECTION_ERROR = FailureSpec(
    code="connection_error",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Connection failed. Please check your network.",
    http_hint=503,
)

SPEC_CLIENT_BAD_REQUEST_ERROR = FailureSpec(
    code="bad_request",
    family="common_client",
    retryable=False,
    requires_user_action=True,
    user_message="Invalid request. Please check your input.",
    http_hint=400,
)

SPEC_CLIENT_UNAUTHORIZED_ERROR = FailureSpec(
    code="unauthorized",
    family="common_client",
    retryable=False,
    requires_user_action=False,
    user_message="Unauthorized. Please log in again.",
    http_hint=401,
)

SPEC_CLIENT_FORBIDDEN_ERROR = FailureSpec(
    code="forbidden",
    family="common_client",
    retryable=False,
    requires_user_action=False,
    user_message="Access forbidden.",
    http_hint=403,
)

SPEC_CLIENT_NOT_FOUND_ERROR = FailureSpec(
    code="not_found",
    family="common_client",
    retryable=False,
    requires_user_action=False,
    user_message="Resource not found.",
    http_hint=404,
)

SPEC_CLIENT_THROTTLED_ERROR = FailureSpec(
    code="throttled",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Rate limited. Please wait a moment.",
    http_hint=429,
)

SPEC_CLIENT_REQUEST_TIMEOUT = FailureSpec(
    code="request_timeout",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Request timed out. Please try again.",
    http_hint=504,
)

SPEC_CLIENT_INCOMPLETE_READ_ERROR = FailureSpec(
    code="incomplete_read",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Incomplete response. Please try again.",
    http_hint=500,
)

SPEC_CLIENT_LOGIN_REQUIRED = FailureSpec(
    code="login_required",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="Login required. Please re-authenticate.",
    http_hint=401,
)

SPEC_RELOGIN_ATTEMPT_EXCEEDED = FailureSpec(
    code="relogin_attempt_exceeded",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="Too many login attempts. Please wait before trying again.",
    http_hint=429,
)

SPEC_CLIENT_ERROR_WITH_TITLE = FailureSpec(
    code="error_with_title",
    family="common_client",
    retryable=False,
    requires_user_action=False,
    user_message="An error occurred.",
    http_hint=400,
)

SPEC_CLIENT_UNKNOWN_ERROR = FailureSpec(
    code="unknown_instagram_error",
    family="unknown",
    retryable=True,
    requires_user_action=False,
    user_message="An unexpected error occurred. Please try again.",
    http_hint=500,
)

SPEC_WRONG_CURSOR_ERROR = FailureSpec(
    code="wrong_cursor",
    family="common_client",
    retryable=False,
    requires_user_action=False,
    user_message="Invalid cursor. Please try again.",
    http_hint=400,
)

SPEC_CLIENT_STATUS_FAIL = FailureSpec(
    code="status_fail",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Status check failed. Please try again.",
    http_hint=500,
)
