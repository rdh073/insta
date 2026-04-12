"""Failure specs for note."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_NOTE_NOT_FOUND = FailureSpec(
    code="note_not_found",
    family="note",
    retryable=False,
    requires_user_action=False,
    user_message="Note not found.",
    http_hint=404,
)
