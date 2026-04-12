"""Post job management use cases - creating, scheduling, listing jobs."""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol

from ..ports.persistence_models import AccountRecord, JobRecord
from ..ports.persistence_uow import PersistenceUnitOfWork

# ============================================================================
# Data Transfer Objects (DTOs)
# ============================================================================


@dataclass
class PostJobDTO:
    """Represents a post job."""
    id: str
    caption: str
    status: str
    media_type: str
    targets: list[dict]
    results: list[dict]
    created_at: str
    media_urls: list[str] = field(default_factory=list)
    scheduled_at: Optional[str] = None


@dataclass
class CreatePostJobRequest:
    """Input for create_post_job use case."""
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
class CreateScheduledPostRequest:
    """Input for create_scheduled_post_draft use case."""
    usernames: list[str]
    caption: str
    scheduled_at: Optional[str] = None


@dataclass
class PostJobResult:
    """Result of creating a post job."""
    job_id: str
    status: str
    targets: list[str]
    not_found: list[str]
    message: str
    error: Optional[str] = None


# ============================================================================
# Port Interfaces (Abstract dependencies)
# ============================================================================


class JobRepository(Protocol):
    """Interface for post job storage."""

    def get(self, job_id: str) -> Optional[JobRecord]:
        """Get job by ID."""
        ...

    def set(self, job_id: str, job: JobRecord) -> None:
        """Store job."""
        ...

    def list_all(self) -> list[JobRecord]:
        """List all jobs."""
        ...


class AccountRepository(Protocol):
    """Interface for account lookups."""

    def get(self, account_id: str) -> Optional[AccountRecord]:
        """Get account metadata."""
        ...

    def find_by_username(self, username: str) -> Optional[str]:
        """Find account ID by username."""
        ...

    def list_all_ids(self) -> list[str]:
        """List all account IDs."""
        ...


class ActivityLogger(Protocol):
    """Interface for activity logging."""

    def log_event(
        self,
        account_id: str,
        username: str,
        event: str,
        detail: Optional[str] = None,
        status: Optional[str] = None,
    ) -> None:
        """Log an account event."""
        ...


# ============================================================================
# Utilities
# ============================================================================


def _utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(datetime.UTC if hasattr(datetime, 'UTC') else None)


def _utc_now_iso() -> str:
    """Get current UTC time in ISO format."""
    now = _utc_now()
    iso = now.isoformat()
    return iso.replace("+00:00", "Z")


def _validate_caption(caption: str) -> str:
    """Validate and clean caption while preserving hashtags and mentions."""
    if not caption:
        return ""
    return caption.strip()


# Shared non-runnable semantics for draft/scheduled jobs without media.
MEDIA_REQUIRED_ERROR_CODE = "media_required"
MEDIA_REQUIRED_ERROR_MESSAGE = "Attach at least one media file before this post can run."
INVALID_SCHEDULE_ERROR_CODE = "invalid_schedule"
INVALID_SCHEDULE_ERROR_MESSAGE = "Scheduled time is invalid. Update it and retry."


def has_runnable_media_paths(media_paths: list[str] | None) -> bool:
    """Return True when at least one non-empty media path is present."""
    if not media_paths:
        return False
    for path in media_paths:
        if isinstance(path, str) and path.strip():
            return True
    return False


def is_valid_scheduled_at(scheduled_at: Optional[str]) -> bool:
    """Return True when scheduled_at is a parseable ISO datetime string."""
    if not isinstance(scheduled_at, str) or not scheduled_at.strip():
        return False
    try:
        datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return False
    return True


# ============================================================================
# Use Case Implementation
# ============================================================================


class PostJobUseCases:
    """Post job management workflows."""

    def __init__(
        self,
        job_repo: JobRepository,
        account_repo: AccountRepository,
        logger: ActivityLogger,
        uow: PersistenceUnitOfWork | None = None,
    ):
        self.job_repo = job_repo
        self.account_repo = account_repo
        self.logger = logger
        self.uow = uow

    def _uow_scope(self):
        if self.uow is None:
            return nullcontext()
        return self.uow

    @staticmethod
    def _account_record(value: AccountRecord | dict | None) -> AccountRecord:
        if value is None:
            return AccountRecord(username="")
        if isinstance(value, AccountRecord):
            return value
        return AccountRecord.from_dict(value)

    @staticmethod
    def _job_record(value: JobRecord | dict) -> JobRecord:
        if isinstance(value, JobRecord):
            return value
        return JobRecord.from_dict(value)

    def create_post_job(self, request: CreatePostJobRequest) -> PostJobDTO:
        """Create a new post job."""
        with self._uow_scope():
            caption = _validate_caption(request.caption)
            initial_status = "scheduled" if request.scheduled_at else "pending"

            # Determine media type: explicit override or infer from files
            inferred = (
                "reels" if any(p.endswith((".mp4", ".mov")) for p in request.media_paths)
                else "album" if len(request.media_paths) > 1
                else "photo"
            )
            media_type = request.media_type or inferred

            if request.thumbnail_path and media_type not in ("reels", "video"):
                raise ValueError("thumbnail only allowed for reels or video")
            if media_type == "igtv" and not request.igtv_title:
                raise ValueError("igtv_title required for IGTV posts")

            job_id = str(uuid.uuid4())
            results = []
            for account_id in request.account_ids:
                account = self._account_record(self.account_repo.get(account_id))
                username = account.username or account_id
                results.append({
                    "accountId": account_id,
                    "username": username,
                    "status": "pending",
                })

            job = JobRecord(
                id=job_id,
                caption=caption,
                media_urls=[],
                media_type=media_type,
                targets=[{"accountId": account_id} for account_id in request.account_ids],
                status=initial_status,
                results=results,
                created_at=_utc_now_iso(),
                media_paths=request.media_paths,
                scheduled_at=request.scheduled_at,
                thumbnail_path=request.thumbnail_path,
                igtv_title=request.igtv_title,
                usertags=request.usertags or [],
                location=request.location,
                extra_data=request.extra_data or {},
            )
            self.job_repo.set(job_id, job)

            return PostJobDTO(
                id=job_id,
                caption=caption,
                status=initial_status,
                media_type=media_type,
                targets=job.targets,
                results=results,
                created_at=job.created_at,
                media_urls=job.media_urls,
                scheduled_at=job.scheduled_at,
            )

    def create_scheduled_post_draft(self, request: CreateScheduledPostRequest) -> PostJobResult:
        """Create a scheduled post draft."""
        with self._uow_scope():
            normalized_usernames = [username.lstrip("@") for username in request.usernames]

            account_ids = []
            not_found = []
            for username in normalized_usernames:
                account_id = self.account_repo.find_by_username(username)
                if account_id:
                    account_ids.append(account_id)
                else:
                    not_found.append(username)

            if not account_ids:
                return PostJobResult(
                    job_id="",
                    status="error",
                    targets=[],
                    not_found=not_found,
                    message="None of the specified accounts were found",
                    error="no_accounts_found",
                )

            job_id = str(uuid.uuid4())
            results = []
            for account_id in account_ids:
                account = self._account_record(self.account_repo.get(account_id))
                username = account.username or account_id
                results.append({
                    "accountId": account_id,
                    "username": username,
                    "status": "pending",
                    "error": MEDIA_REQUIRED_ERROR_MESSAGE,
                    "errorCode": MEDIA_REQUIRED_ERROR_CODE,
                })

            job = JobRecord(
                id=job_id,
                caption=request.caption,
                media_urls=[],
                media_type="photo",
                targets=[{"accountId": account_id} for account_id in account_ids],
                status="needs_media",
                results=results,
                created_at=_utc_now_iso(),
                media_paths=[],
                scheduled_at=request.scheduled_at,
            )
            self.job_repo.set(job_id, job)

            target_usernames = [
                self._account_record(self.account_repo.get(account_id)).username
                for account_id in account_ids
            ]

            if request.scheduled_at:
                message = (
                    f"Post draft created for {', '.join('@' + u for u in target_usernames)} "
                    f"at {request.scheduled_at}. Attach media via the Post page to activate scheduling."
                )
            else:
                message = (
                    f"Caption draft created for {', '.join('@' + u for u in target_usernames)}. "
                    f"Attach media via the Post page to publish."
                )

            return PostJobResult(
                job_id=job_id,
                status=job.status,
                targets=target_usernames,
                not_found=not_found,
                message=message,
            )

    def retry_job(self, job_id: str) -> JobRecord:
        """Reset a failed/stopped/partial job so it can be re-executed.

        Only failed or pending (not-yet-attempted) results are reset back to
        pending — successful results are preserved so accounts that already
        posted are not posted to again.
        """
        job_record = self.job_repo.get(job_id)
        if job_record is None:
            raise ValueError(f"Job {job_id!r} not found")
        retryable = {"failed", "stopped", "partial"}
        if job_record.status not in retryable:
            raise ValueError(
                f"Cannot retry job with status '{job_record.status}'. "
                f"Only {retryable} jobs can be retried."
            )

        reset_results = []
        for r in job_record.results:
            if r.get("status") in ("failed", "pending", "skipped"):
                reset_results.append({**r, "status": "pending", "error": None})
            else:
                reset_results.append(r)

        updated = JobRecord(
            id=job_record.id,
            caption=job_record.caption,
            status="pending",
            targets=job_record.targets,
            results=reset_results,
            created_at=job_record.created_at,
            media_urls=job_record.media_urls,
            media_type=job_record.media_type,
            media_paths=job_record.media_paths,
            scheduled_at=None,
            thumbnail_path=job_record.thumbnail_path,
            igtv_title=job_record.igtv_title,
            usertags=job_record.usertags,
            location=job_record.location,
            extra_data=job_record.extra_data,
        )
        self.job_repo.set(job_id, updated)
        return updated

    def delete_job(self, job_id: str) -> None:
        """Delete a job.  Raises ValueError if not found or still active."""
        job_record = self.job_repo.get(job_id)
        if job_record is None:
            raise ValueError(f"Job {job_id!r} not found")
        active = {"pending", "scheduled", "running", "paused"}
        if job_record.status in active:
            raise ValueError(
                f"Cannot delete job with status '{job_record.status}'. Stop it first."
            )
        self.job_repo.delete(job_id)

    def list_posts(self) -> list[PostJobDTO]:
        """List all posts (jobs)."""
        jobs = [self._job_record(job) for job in self.job_repo.list_all()]
        results = []
        for job in jobs:
            results.append(PostJobDTO(
                id=job.id,
                caption=job.caption,
                status=job.status,
                media_type=job.media_type,
                targets=job.targets,
                results=job.results,
                created_at=job.created_at,
                media_urls=job.media_urls,
                scheduled_at=job.scheduled_at,
            ))
        return results

    def list_recent_posts(self, limit: int = 10, status_filter: Optional[str] = None) -> dict:
        """List recent post jobs."""
        jobs = [self._job_record(job) for job in self.job_repo.list_all()]
        if status_filter:
            jobs = [job for job in jobs if job.status == status_filter]

        jobs = jobs[-limit:]

        return {
            "jobs": [
                {
                    "id": job.id,
                    "status": job.status,
                    "caption": (job.caption[:80] + "…")
                    if len(job.caption) > 80
                    else job.caption,
                    "targets": len(job.targets),
                    "createdAt": job.created_at,
                    "results": [
                        {"username": result["username"], "status": result["status"]}
                        for result in job.results
                    ],
                }
                for job in jobs
            ],
            "total": len(jobs),
        }

    def create_scheduled_post_for_usernames(
        self,
        usernames: list[str],
        caption: str,
        scheduled_at: Optional[str] = None,
    ) -> dict:
        """Create a scheduled post draft for usernames (for AI tools)."""
        request = CreateScheduledPostRequest(
            usernames=usernames,
            caption=caption,
            scheduled_at=scheduled_at,
        )
        result = self.create_scheduled_post_draft(request)
        return {
            "success": result.error is None,
            "jobId": result.job_id,
            "status": result.status,
            "targets": result.targets,
            "not_found": result.not_found,
            "scheduled_at": scheduled_at,
            "message": result.message,
            "error": result.error,
        }
