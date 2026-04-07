"""
Instagram highlight DTOs - application-owned contracts for highlight data.

Separates highlight read/write concerns from vendor Highlight and Story types.
Prevents instagrapi Highlight and nested Story objects from leaking into
application or AI layers.

Reuses StorySummary from the shared story DTO module instead of defining
a second highlight-only story summary. This keeps story mapping centralized
in the phase 4 boundary.

All DTOs are frozen (immutable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.application.dto.instagram_story_dto import StorySummary


@dataclass(frozen=True)
class HighlightCoverSummary:
    """Cover image metadata for a highlight.

    Extracts only the cover image URL and crop rectangle, leaving
    full cover_media extraction to the adapter.
    """
    media_id: Optional[str] = None
    image_url: Optional[str] = None
    crop_rect: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class HighlightSummary:
    """Minimal highlight metadata for lists and quick lookups.

    Represents a highlight without detailed story information.
    """
    pk: str
    highlight_id: str
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    is_pinned: Optional[bool] = None
    media_count: Optional[int] = None
    latest_reel_media: Optional[int] = None
    owner_username: Optional[str] = None
    cover: Optional[HighlightCoverSummary] = None


@dataclass(frozen=True)
class HighlightDetail:
    """Highlight with full story content.

    Includes summary information plus list of story IDs and full StorySummary items.
    Stories are mapped through the shared phase 4 story DTO seam, not as vendor objects.
    """
    summary: HighlightSummary
    story_ids: list[str] = field(default_factory=list)
    items: list[StorySummary] = field(default_factory=list)


@dataclass(frozen=True)
class HighlightActionReceipt:
    """Result of a highlight action (create, delete, etc.).

    Provides stable feedback on highlight operations.
    """
    action_id: str
    success: bool
    reason: str = ""
