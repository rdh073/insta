"""Instagram analytics and music track DTOs.

Provides stable contracts for insights (post-level analytics) and tracks (music metadata).
These DTOs prevent instagrapi analytics payloads and Track vendor objects from leaking
into the application layer.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class MediaInsightSummary:
    """Post/media-level insight metrics.

    Normalizes common Instagram insight metrics into stable internal field names.
    Unknown vendor metrics are captured in extra_metrics instead of leaking raw dicts.
    All metric counts are None if unavailable rather than 0.
    """

    media_pk: int
    """Instagram media/post PK (primary key)."""

    reach_count: Optional[int] = None
    """Number of accounts that have seen this post."""

    impression_count: Optional[int] = None
    """Total number of times this post was seen (accounts may see it multiple times)."""

    like_count: Optional[int] = None
    """Total likes on the post."""

    comment_count: Optional[int] = None
    """Total comments on the post."""

    share_count: Optional[int] = None
    """Total times post was shared/sent as a DM."""

    save_count: Optional[int] = None
    """Total times post was saved."""

    video_view_count: Optional[int] = None
    """Total times video was viewed (for video posts only)."""

    profile_view_count: Optional[int] = None
    """Total profile views from this post."""

    extra_metrics: dict = field(default_factory=dict)
    """Unmapped vendor metrics stored as key-value pairs.

    Captures vendor-specific or newer Instagram metrics not yet modeled.
    Keys are vendor field names, values can be int, float, str, or None.
    """


@dataclass(frozen=True)
class AccountInsightSummary:
    """Account-level insight metrics.

    Normalizes Instagram's account dashboard metrics (followers, reach,
    impressions, profile activity) into stable internal fields. Unknown
    vendor metrics are captured in extra_metrics instead of leaking raw dicts.
    All metric counts are None if unavailable rather than 0.
    """

    followers_count: Optional[int] = None
    """Total accounts following this profile."""

    following_count: Optional[int] = None
    """Total accounts this profile follows."""

    media_count: Optional[int] = None
    """Total media items published on this profile."""

    impressions_last_7_days: Optional[int] = None
    """Total impressions across the last 7 days."""

    reach_last_7_days: Optional[int] = None
    """Unique accounts reached in the last 7 days."""

    profile_views_last_7_days: Optional[int] = None
    """Profile views in the last 7 days."""

    website_clicks_last_7_days: Optional[int] = None
    """Website-link clicks in the last 7 days."""

    follower_change_last_7_days: Optional[int] = None
    """Net follower change (gained minus lost) in the last 7 days."""

    extra_metrics: dict = field(default_factory=dict)
    """Unmapped vendor metrics stored as key-value pairs.

    Captures vendor-specific or newer Instagram metrics not yet modeled.
    Keys are vendor field names, values can be int, float, str, or None.
    """


@dataclass(frozen=True)
class TrackSummary:
    """Music track summary for search results and catalog lookups.

    Contains core track metadata needed for display and selection.
    """

    canonical_id: str
    """Stable identifier for the track across Instagram platform."""

    title: Optional[str] = None
    """Track/song title."""

    artist_name: Optional[str] = None
    """Primary artist name."""

    duration_in_ms: Optional[int] = None
    """Track duration in milliseconds."""


@dataclass(frozen=True)
class TrackDetail:
    """Extended track metadata for detailed view.

    Includes summary plus additional fields useful for previews/selection UI.
    """

    summary: TrackSummary
    """Core track metadata."""

    uri: Optional[str] = None
    """Track URI (used for download and publishing)."""

    display_artist: Optional[str] = None
    """Display name for artist (may differ from canonical artist_name)."""


@dataclass(frozen=True)
class TrackReference:
    """Internal track reference for publishing workflows.

    This is the type that publishing flows (reels, clips) should accept,
    NOT vendor Track. Allows adapters to construct vendor Track objects
    only at the publishing boundary.
    """

    canonical_id: str
    """Stable identifier for the track."""

    title: Optional[str] = None
    """Track/song title."""

    artist_name: Optional[str] = None
    """Primary artist name."""
