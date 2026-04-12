"""Failure specs for igtv."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_IGTV_NOT_UPLOAD = FailureSpec(
    code="igtv_upload_failed",
    family="igtv",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to upload IGTV video. Try again.",
    http_hint=500,
)

SPEC_IGTV_CONFIGURE_ERROR = FailureSpec(
    code="igtv_configure_error",
    family="igtv",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to configure IGTV video. Try again.",
    http_hint=500,
)
