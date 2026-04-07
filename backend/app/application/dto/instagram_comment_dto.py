"""
Instagram comment DTOs - application-owned contracts for comment data.

Separates comment read/write concerns from vendor Comment types.
Prevents instagrapi Comment objects from leaking into application or AI layers.

All DTOs are frozen (immutable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class CommentAuthorSummary:
    """Comment author metadata.

    Represents the user who created a comment.
    """
    pk: int
    username: str
    full_name: Optional[str] = None
    profile_pic_url: Optional[str] = None


@dataclass(frozen=True)
class CommentSummary:
    """Minimal comment metadata for lists and display.

    Represents a comment without reply threading or detailed composition.
    """
    pk: int
    text: str
    author: CommentAuthorSummary
    created_at: Optional[datetime] = None
    content_type: Optional[str] = None
    status: Optional[str] = None
    has_liked: Optional[bool] = None
    like_count: Optional[int] = None


@dataclass(frozen=True)
class CommentPage:
    """Paginated comment results with cursor for iteration.

    Encapsulates both comment data and pagination state.
    """
    comments: list[CommentSummary] = field(default_factory=list)
    next_cursor: Optional[str] = None


@dataclass(frozen=True)
class CommentActionReceipt:
    """Result of a comment action (create, delete, etc.).

    Provides stable feedback on comment operations.
    """
    action_id: str
    success: bool
    reason: str = ""
