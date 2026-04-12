"""Failure specs for photo."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_PHOTO_NOT_DOWNLOAD = FailureSpec(
    code="photo_download_failed",
    family="photo",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to download photo. Try again.",
    http_hint=500,
)

SPEC_PHOTO_NOT_UPLOAD = FailureSpec(
    code="photo_upload_failed",
    family="photo",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to upload photo. Try again.",
    http_hint=500,
)

SPEC_PHOTO_CONFIGURE_ERROR = FailureSpec(
    code="photo_configure_error",
    family="photo",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to configure photo. Try again.",
    http_hint=500,
)

SPEC_PHOTO_CONFIGURE_STORY_ERROR = FailureSpec(
    code="photo_story_configure_error",
    family="photo",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to post photo story. Try again.",
    http_hint=500,
)
