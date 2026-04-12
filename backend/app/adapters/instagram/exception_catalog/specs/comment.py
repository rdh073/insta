"""Failure specs for comment."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_COMMENT_NOT_FOUND = FailureSpec(
    code="comment_not_found",
    family="comment",
    retryable=False,
    requires_user_action=False,
    user_message="Comment not found.",
    http_hint=404,
)

SPEC_COMMENTS_DISABLED = FailureSpec(
    code="comments_disabled",
    family="comment",
    retryable=False,
    requires_user_action=False,
    user_message="Comments are disabled on this post.",
    http_hint=403,
)
