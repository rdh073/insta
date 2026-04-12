"""Failure specs for reels/clip."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_CLIP_NOT_UPLOAD = FailureSpec(
    code="clip_upload_failed",
    family="clip",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to upload clip. Try again.",
    http_hint=500,
)

SPEC_CLIP_CONFIGURE_ERROR = FailureSpec(
    code="clip_configure_error",
    family="clip",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to configure clip. Try again.",
    http_hint=500,
)
