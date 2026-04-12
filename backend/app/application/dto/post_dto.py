"""Post job-related DTOs for request/response boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CreatePostJobRequest:
    """Input for creating a post job."""
    caption: str
    account_ids: list[str]
    media_paths: list[str]
    scheduled_at: Optional[str] = None
    media_type: Optional[str] = None
    thumbnail_path: Optional[str] = None
    igtv_title: Optional[str] = None
    usertags: Optional[list[dict]] = None
    location: Optional[dict] = None
    extra_data: Optional[dict] = None


@dataclass
class PostJobResponse:
    """Output for post job operations."""
    id: str
    caption: str
    status: str
    media_type: str
    targets: list[dict]
    results: list[dict]
    created_at: str
    media_urls: list[str] = None


@dataclass
class CreateScheduledPostRequest:
    """Input for creating a scheduled post draft."""
    usernames: list[str]
    caption: str
    scheduled_at: Optional[str] = None


@dataclass
class PostJobListResponse:
    """Output for listing post jobs."""
    jobs: list[dict]
    total: int
