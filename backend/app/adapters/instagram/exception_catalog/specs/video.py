"""Failure specs for video."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_VIDEO_NOT_DOWNLOAD = FailureSpec(
    code="video_download_failed",
    family="video",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to download video. Try again.",
    http_hint=500,
)

SPEC_VIDEO_NOT_UPLOAD = FailureSpec(
    code="video_upload_failed",
    family="video",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to upload video. Try again.",
    http_hint=500,
)

SPEC_VIDEO_CONFIGURE_ERROR = FailureSpec(
    code="video_configure_error",
    family="video",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to configure video. Try again.",
    http_hint=500,
)

SPEC_VIDEO_CONFIGURE_STORY_ERROR = FailureSpec(
    code="video_story_configure_error",
    family="video",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to post video story. Try again.",
    http_hint=500,
)

SPEC_VIDEO_TOO_LONG_EXCEPTION = FailureSpec(
    code="video_too_long",
    family="video",
    retryable=False,
    requires_user_action=True,
    user_message="Video is too long.",
    http_hint=400,
)
