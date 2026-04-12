"""Failure specs for track."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_TRACK_NOT_FOUND = FailureSpec(
    code="track_not_found",
    family="track",
    retryable=False,
    requires_user_action=False,
    user_message="Track not found.",
    http_hint=404,
)
