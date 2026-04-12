"""Failure specs for media."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_MEDIA_ERROR = FailureSpec(
    code="media_error",
    family="media",
    retryable=False,
    requires_user_action=False,
    user_message="Media operation failed.",
    http_hint=400,
)

SPEC_MEDIA_NOT_FOUND = FailureSpec(
    code="media_not_found",
    family="media",
    retryable=False,
    requires_user_action=False,
    user_message="Media not found.",
    http_hint=404,
)

SPEC_INVALID_TARGET_USER = FailureSpec(
    code="invalid_target_user",
    family="media",
    retryable=False,
    requires_user_action=False,
    user_message="Invalid target user.",
    http_hint=400,
)

SPEC_INVALID_MEDIA_ID = FailureSpec(
    code="invalid_media_id",
    family="media",
    retryable=False,
    requires_user_action=False,
    user_message="Invalid media ID.",
    http_hint=400,
)

SPEC_MEDIA_UNAVAILABLE = FailureSpec(
    code="media_unavailable",
    family="media",
    retryable=False,
    requires_user_action=False,
    user_message="Media is unavailable.",
    http_hint=403,
)
