"""Failure specs for collection."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_COLLECTION_ERROR = FailureSpec(
    code="collection_error",
    family="collection",
    retryable=False,
    requires_user_action=False,
    user_message="Collection operation failed.",
    http_hint=400,
)

SPEC_COLLECTION_NOT_FOUND = FailureSpec(
    code="collection_not_found",
    family="collection",
    retryable=False,
    requires_user_action=False,
    user_message="Collection not found.",
    http_hint=404,
)
