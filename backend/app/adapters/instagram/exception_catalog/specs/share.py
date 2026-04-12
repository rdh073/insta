"""Failure specs for share."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_SHARE_DECODE_ERROR = FailureSpec(
    code="share_decode_error",
    family="share",
    retryable=False,
    requires_user_action=False,
    user_message="Failed to decode share link.",
    http_hint=400,
)
