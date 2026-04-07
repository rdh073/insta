"""Direct-message vertical domain entrypoint."""

from __future__ import annotations

from .aggregates_core import DirectMessageAggregate, DirectThreadAggregate
from .services_core import DirectThreadService
from .interaction_values_core import (
    DirectThreadID,
    DirectMessageID,
    UserIDList,
    ThreadMessageLimit,
    SearchQuery,
    QueryAmount,
    CommentText,
    InvalidIdentifier,
    InvalidComposite,
)

__all__ = [
    "DirectMessageAggregate",
    "DirectThreadAggregate",
    "DirectThreadService",
    "DirectThreadID",
    "DirectMessageID",
    "UserIDList",
    "ThreadMessageLimit",
    "SearchQuery",
    "QueryAmount",
    "CommentText",
    "InvalidIdentifier",
    "InvalidComposite",
]
