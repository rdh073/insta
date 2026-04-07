"""
Instagram story DTOs - application-owned contracts for story data and composition.

Separates story read/write concerns and composition specs from vendor Story and
sticker types. Prevents instagrapi Story, StoryLink, StoryMention, etc. from
leaking into application or AI layers.

All specs are frozen (immutable) and define placement geometry for overlays.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional


@dataclass(frozen=True)
class StorySummary:
    """Minimal story metadata for lists and quick lookups.

    Represents a story without detailed overlay information.
    """
    pk: int
    story_id: str
    media_type: Optional[int] = None
    taken_at: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    video_url: Optional[str] = None
    viewer_count: Optional[int] = None
    owner_username: Optional[str] = None


@dataclass(frozen=True)
class StoryDetail:
    """Story with detailed overlay counts.

    Used when inspecting story composition to understand what overlays are present.
    """
    summary: StorySummary
    link_count: int = 0
    mention_count: int = 0
    hashtag_count: int = 0
    location_count: int = 0
    sticker_count: int = 0


@dataclass(frozen=True)
class StoryLinkSpec:
    """Link overlay specification for story publishing.

    Defines a swipe-up style link to be rendered as an interactive sticker.
    """
    web_uri: str


@dataclass(frozen=True)
class StoryLocationSpec:
    """Location overlay specification for story publishing.

    Defines a location sticker with placement geometry on the story canvas.
    """
    location_pk: Optional[int] = None
    name: Optional[str] = None
    x: float = 0.5
    y: float = 0.5
    width: float = 0.2
    height: float = 0.2


@dataclass(frozen=True)
class StoryMentionSpec:
    """User mention overlay specification for story publishing.

    Defines a user mention with placement geometry on the story canvas.
    Coordinates and dimensions are normalized to [0, 1] range.
    """
    user_id: int
    username: Optional[str] = None
    x: float = 0.5
    y: float = 0.5
    width: float = 0.2
    height: float = 0.2


@dataclass(frozen=True)
class StoryHashtagSpec:
    """Hashtag overlay specification for story publishing.

    Defines a hashtag sticker with placement geometry on the story canvas.
    """
    hashtag_name: str
    hashtag_id: Optional[int] = None
    x: float = 0.5
    y: float = 0.5
    width: float = 0.2
    height: float = 0.2


@dataclass(frozen=True)
class StoryStickerSpec:
    """Generic sticker overlay specification for story publishing.

    Covers stickers like Giphy GIF tags and other non-standard overlays.
    Maps to instagrapi StorySticker(id, type, x, y, width, height).
    Coordinates and dimensions are optional (defaults applied at adapter boundary).
    """
    sticker_type: str
    sticker_id: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass(frozen=True)
class StoryPollSpec:
    """Poll overlay specification for story publishing.

    Maps to instagrapi StoryPoll(question, options, x, y, width, height).
    Instagram requires exactly 2 options for a standard binary poll.
    """
    question: str
    options: tuple[str, ...]
    x: float = 0.5
    y: float = 0.5
    width: float = 0.7
    height: float = 0.5


@dataclass(frozen=True)
class StoryMediaSpec:
    """Reshared post overlay specification for story publishing.

    Maps to instagrapi StoryMedia(media_pk, x, y, width, height, rotation).
    Embeds a feed post as an interactive sticker on the story canvas.
    """
    media_pk: int
    x: float = 0.5
    y: float = 0.5
    width: float = 0.8
    height: float = 0.6
    rotation: float = 0.0


@dataclass(frozen=True)
class StoryPublishRequest:
    """Request to publish a story with optional overlays.

    Centralizes all story publication inputs: media path, caption, audience, and
    composition specs (links, mentions, hashtags, locations, stickers).

    Adapter is responsible for:
    - Choosing photo_upload_to_story or video_upload_to_story based on media_kind
    - Mapping audience="close_friends" to vendor extra_data={"audience": "besties"}
    - Building vendor StoryLink, StoryMention, etc. from spec fields
    - Handling thumbnail path and 9:16 media preparation
    """
    media_path: str
    media_kind: Literal["photo", "video"]
    caption: Optional[str] = None
    thumbnail_path: Optional[str] = None
    audience: Literal["default", "close_friends"] = "default"
    links: list[StoryLinkSpec] = field(default_factory=list)
    locations: list[StoryLocationSpec] = field(default_factory=list)
    mentions: list[StoryMentionSpec] = field(default_factory=list)
    hashtags: list[StoryHashtagSpec] = field(default_factory=list)
    stickers: list[StoryStickerSpec] = field(default_factory=list)
    polls: list[StoryPollSpec] = field(default_factory=list)
    medias: list[StoryMediaSpec] = field(default_factory=list)


@dataclass(frozen=True)
class StoryActionReceipt:
    """Result of a story action (publish, delete, mark_seen, etc.).

    Provides stable feedback on story operations.
    """
    action_id: str
    success: bool
    reason: str = ""
