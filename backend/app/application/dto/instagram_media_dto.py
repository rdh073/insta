"""
Instagram media DTOs - stable contracts for media, resources, and oembed data.

Isolates vendor media models (Media, Resource, MediaOembed) from
application logic and AI workflows.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass(frozen=True)
class ResourceSummary:
    """
    Summary of a media resource (album item).

    Represents a single resource within a carousel/album post.
    Each resource is either a photo or video.
    """

    pk: int
    """Instagram resource ID."""

    media_type: int
    """Media type: 1=photo, 2=video, 8=album."""

    thumbnail_url: Optional[str] = None
    """URL to resource thumbnail/preview image."""

    video_url: Optional[str] = None
    """URL to video file (None for photos)."""


@dataclass(frozen=True)
class MediaSummary:
    """
    Summary of an Instagram media post.

    Represents a single post (photo, video, carousel, reel, etc).
    Includes metadata like engagement counts and caption.
    """

    pk: int
    """Instagram media primary key."""

    media_id: str
    """Instagram media ID (alternative identifier)."""

    code: str
    """Instagram media code (short URL identifier)."""

    media_type: int
    """Media type: 1=photo, 2=video, 8=album, etc."""

    product_type: str
    """Product type: feed, stories, clips, igtv, reels, etc."""

    owner_username: Optional[str] = None
    """Username of post author."""

    caption_text: str = ""
    """Post caption text. Empty string if no caption."""

    like_count: int = 0
    """Number of likes."""

    comment_count: int = 0
    """Number of comments."""

    taken_at: Optional[datetime] = None
    """Timestamp when media was taken/created."""

    resources: list[ResourceSummary] = field(default_factory=list)
    """
    Album/carousel resources (empty list for single-photo posts).
    Each resource is a photo or video in the carousel.
    """


@dataclass(frozen=True)
class MediaActionReceipt:
    """
    Result of a media write mutation (edit/delete/pin/archive/save/etc).

    Mirrors CommentActionReceipt so HTTP responses are uniform across
    media mutation endpoints.
    """

    action_id: str
    """Identifier of the affected media (typically the media_id)."""

    success: bool
    """Whether the vendor call succeeded."""

    reason: str
    """Human-readable description (success or translated failure message)."""


@dataclass(frozen=True)
class MediaOembedSummary:
    """
    oEmbed summary for an Instagram media URL.

    Represents the response from media_oembed() which returns
    limited metadata suitable for embedding.
    """

    media_id: str
    """Instagram media ID."""

    author_name: Optional[str] = None
    """Username of post author."""

    author_url: Optional[str] = None
    """URL to author profile."""

    author_id: Optional[int] = None
    """Author's Instagram user ID."""

    title: Optional[str] = None
    """Post caption (if available in oembed)."""

    provider_name: Optional[str] = None
    """Provider name (typically 'Instagram')."""

    html: Optional[str] = None
    """Embedded HTML (treat as opaque - do not parse in application code)."""

    thumbnail_url: Optional[str] = None
    """URL to media thumbnail."""

    width: Optional[int] = None
    """Thumbnail/embed width in pixels."""

    height: Optional[int] = None
    """Thumbnail/embed height in pixels."""

    can_view: Optional[bool] = None
    """Whether the authenticated account can view the media."""
