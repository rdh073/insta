"""Failure specs for location."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_LOCATION_ERROR = FailureSpec(
    code="location_error",
    family="location",
    retryable=False,
    requires_user_action=False,
    user_message="Location operation failed.",
    http_hint=400,
)

SPEC_LOCATION_NOT_FOUND = FailureSpec(
    code="location_not_found",
    family="location",
    retryable=False,
    requires_user_action=False,
    user_message="Location not found.",
    http_hint=404,
)
