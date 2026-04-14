"""Strict post-job scheduling contract for AI copilot runtime adapters."""

from __future__ import annotations

from typing import Any, Protocol

_REQUIRED_METHOD_NAME = "create_scheduled_post_for_usernames"


class PostJobCapabilityUnavailableError(RuntimeError):
    """Raised when the post-job adapter misses required scheduling capability."""


class PostJobContractError(RuntimeError):
    """Raised when post-job scheduler returns an invalid payload shape."""


class PostJobSchedulerPort(Protocol):
    """Minimal capability required by AI copilot scheduler-facing adapters."""

    def create_scheduled_post_for_usernames(
        self,
        usernames: list[str],
        caption: str,
        scheduled_at: str | None = None,
    ) -> dict[str, Any]:
        """Create a scheduled post draft for target usernames."""


class StrictPostJobSchedulerPort:
    """Runtime guard around post-job use cases with strict contract checks."""

    def __init__(self, postjob_usecases: object) -> None:
        self._postjob_usecases = postjob_usecases

    def create_scheduled_post_for_usernames(
        self,
        usernames: list[str],
        caption: str,
        scheduled_at: str | None = None,
    ) -> dict[str, Any]:
        method = getattr(self._postjob_usecases, _REQUIRED_METHOD_NAME, None)
        if not callable(method):
            raise PostJobCapabilityUnavailableError(
                "Missing required post-job capability: "
                f"'{_REQUIRED_METHOD_NAME}(usernames, caption, scheduled_at)'"
            )

        result = method(
            usernames=usernames,
            caption=caption,
            scheduled_at=scheduled_at,
        )
        return _normalize_schedule_result(result, scheduled_at=scheduled_at)


def _normalize_schedule_result(result: object, *, scheduled_at: str | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise PostJobContractError(
            "Post-job scheduler contract violation: expected dict result, "
            f"got {type(result).__name__}"
        )

    job_id = str(result.get("job_id") or result.get("jobId") or "").strip()
    status = str(result.get("status") or "").strip().lower()
    if not job_id:
        raise PostJobContractError(
            "Post-job scheduler contract violation: missing non-empty 'job_id'/'jobId'"
        )
    if not status:
        raise PostJobContractError(
            "Post-job scheduler contract violation: missing non-empty 'status'"
        )

    resolved_scheduled_at = result.get("scheduled_at", result.get("scheduledAt", scheduled_at))
    if resolved_scheduled_at is not None and not isinstance(resolved_scheduled_at, str):
        resolved_scheduled_at = str(resolved_scheduled_at)

    return {
        "job_id": job_id,
        "status": status,
        "scheduled_at": resolved_scheduled_at,
    }
