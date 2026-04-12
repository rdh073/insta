"""Failure specs for direct."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_DIRECT_ERROR = FailureSpec(
    code="direct_error",
    family="direct",
    retryable=False,
    requires_user_action=False,
    user_message="Direct message operation failed.",
    http_hint=400,
)

SPEC_DIRECT_THREAD_NOT_FOUND = FailureSpec(
    code="direct_thread_not_found",
    family="direct",
    retryable=False,
    requires_user_action=False,
    user_message="Direct thread not found.",
    http_hint=404,
)

SPEC_DIRECT_MESSAGE_NOT_FOUND = FailureSpec(
    code="direct_message_not_found",
    family="direct",
    retryable=False,
    requires_user_action=False,
    user_message="Direct message not found.",
    http_hint=404,
)
