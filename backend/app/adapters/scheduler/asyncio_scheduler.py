"""Legacy asyncio scheduler — kept for backward compatibility only.

New code should use ``PostJobQueue`` instead.
"""

from __future__ import annotations

from typing import Optional

from app.adapters.instagram import InstagramClientAdapter


class AsyncioScheduler:
    """Thin wrapper that runs a post job synchronously.

    Retained so that any code still referencing ``AsyncioScheduler`` does
    not break.  All real scheduling now goes through ``PostJobQueue``.
    """

    def __init__(self) -> None:
        self._ig = InstagramClientAdapter()

    def schedule_post_job_sync(self, job_id: str, scheduled_at: Optional[str] = None) -> None:
        self._ig.run_post_job(job_id)
