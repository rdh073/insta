"""Failure specs for album."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_ALBUM_NOT_DOWNLOAD = FailureSpec(
    code="album_download_failed",
    family="album",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to download album. Try again.",
    http_hint=500,
)

SPEC_ALBUM_UNKNOWN_FORMAT = FailureSpec(
    code="album_unknown_format",
    family="album",
    retryable=False,
    requires_user_action=False,
    user_message="Unknown album format.",
    http_hint=400,
)

SPEC_ALBUM_CONFIGURE_ERROR = FailureSpec(
    code="album_configure_error",
    family="album",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to configure album. Try again.",
    http_hint=500,
)
