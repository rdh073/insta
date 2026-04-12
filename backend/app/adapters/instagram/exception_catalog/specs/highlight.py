"""Failure specs for highlight."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_HIGHLIGHT_NOT_FOUND = FailureSpec(
    code="highlight_not_found",
    family="highlight",
    retryable=False,
    requires_user_action=False,
    user_message="Highlight not found.",
    http_hint=404,
)
