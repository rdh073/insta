"""Failure specs for story."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_STORY_NOT_FOUND = FailureSpec(
    code="story_not_found",
    family="story",
    retryable=False,
    requires_user_action=False,
    user_message="Story not found.",
    http_hint=404,
)
