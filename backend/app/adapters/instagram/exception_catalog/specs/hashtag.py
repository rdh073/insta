"""Failure specs for hashtag."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_HASHTAG_ERROR = FailureSpec(
    code="hashtag_error",
    family="hashtag",
    retryable=False,
    requires_user_action=False,
    user_message="Hashtag operation failed.",
    http_hint=400,
)

SPEC_HASHTAG_NOT_FOUND = FailureSpec(
    code="hashtag_not_found",
    family="hashtag",
    retryable=False,
    requires_user_action=False,
    user_message="Hashtag not found.",
    http_hint=404,
)

SPEC_HASHTAG_PAGE_WARNING = FailureSpec(
    code="hashtag_page_warning",
    family="hashtag",
    retryable=False,
    requires_user_action=False,
    user_message="Hashtag page warning.",
    http_hint=400,
)
