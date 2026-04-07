"""
Instagram discovery DTOs - application-owned contracts for location and hashtag data.

Separates discovery reads (public Location, Hashtag) from application logic.
Prevents instagrapi Location, Hashtag vendor models from leaking into
application or AI layers.

All DTOs are frozen (immutable) and contain only essential metadata.
Media results use the shared MediaSummary contract, not raw vendor Media.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LocationSummary:
    """Minimal location metadata for discovery and search results.

    Represents a geographic location that can be searched or browsed for posts.
    """
    pk: int
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    external_id: Optional[int] = None
    external_id_source: Optional[str] = None


@dataclass(frozen=True)
class HashtagSummary:
    """Minimal hashtag metadata for discovery and search results.

    Represents a hashtag that can be searched or browsed for posts.
    """
    id: int
    name: str
    media_count: Optional[int] = None
    profile_pic_url: Optional[str] = None


@dataclass(frozen=True)
class CollectionSummary:
    """Minimal collection metadata for authenticated user's saved collections.

    Collections are authenticated/self-owned saved state, not public discovery objects.
    Use to enumerate or inspect user's saved collections.
    """
    pk: int
    name: str
    media_count: Optional[int] = None
