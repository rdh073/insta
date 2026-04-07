"""Comment vertical domain entrypoint."""

from __future__ import annotations

from .aggregates_core import CommentAggregate
from .services_core import CommentThreadService
from .interaction_values_core import (
    CommentID,
    CommentText,
    OptionalReplyTarget,
    MediaID,
    PageSize,
    QueryAmount,
    InvalidIdentifier,
    InvalidComposite,
)

__all__ = [
    "CommentAggregate",
    "CommentThreadService",
    "CommentID",
    "CommentText",
    "OptionalReplyTarget",
    "MediaID",
    "PageSize",
    "QueryAmount",
    "InvalidIdentifier",
    "InvalidComposite",
]
