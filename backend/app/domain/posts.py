"""Domain entities for post job management."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PostJobStatus(str, Enum):
    """Post job lifecycle states."""
    PENDING = "pending"
    NEEDS_MEDIA = "needs_media"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    STOPPED = "stopped"


class MediaType(str, Enum):
    """Type of media in post job."""
    PHOTO = "photo"
    VIDEO = "video"
    ALBUM = "album"


@dataclass
class PostTarget:
    """Target account for a post job."""
    account_id: str


@dataclass
class PostResult:
    """Result of posting to a single account."""
    account_id: str
    username: str
    status: str  # "pending", "success", "failed"
    error: Optional[str] = None


@dataclass
class PostJob:
    """Core post job entity."""

    id: str
    caption: str
    status: PostJobStatus = PostJobStatus.PENDING
    media_type: MediaType = MediaType.PHOTO
    targets: list[PostTarget] = field(default_factory=list)
    results: list[PostResult] = field(default_factory=list)
    created_at: str = ""
    media_urls: list[str] = field(default_factory=list)
    scheduled_at: Optional[str] = None

    # Internal fields (not exposed in API)
    _media_paths: list[str] = field(default_factory=list, init=False, repr=False)

    def validate(self) -> None:
        """Validate post job invariants."""
        if not self.id:
            raise ValueError("Post job must have an ID")
        if not self.caption:
            raise ValueError("Post job must have a caption")
        if not self.targets:
            raise ValueError("Post job must have at least one target")

    def is_complete(self) -> bool:
        """Check if job execution is complete."""
        return self.status in (
            PostJobStatus.COMPLETED,
            PostJobStatus.PARTIAL,
            PostJobStatus.FAILED,
        )

    def is_pending(self) -> bool:
        """Check if job is awaiting execution."""
        return self.status in (
            PostJobStatus.PENDING,
            PostJobStatus.NEEDS_MEDIA,
        )
