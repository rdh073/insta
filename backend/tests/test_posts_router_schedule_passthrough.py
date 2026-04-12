"""Posts router contract tests for scheduled post creation."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import UploadFile

from app.adapters.http.routers.posts import create_post


class _StubPostUseCases:
    def __init__(self) -> None:
        self.create_request = None

    def create_post_job(self, request):
        self.create_request = request
        return SimpleNamespace(
            id="job-1",
            caption=request.caption,
            status="scheduled",
            media_type=request.media_type or "photo",
            targets=[{"accountId": "acc-1"}],
            results=[{"accountId": "acc-1", "status": "pending"}],
            created_at="2026-04-12T00:00:00Z",
            media_urls=[],
        )


class _StubScheduler:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, str | None]] = []

    def enqueue(self, job_id: str, scheduled_at: str | None = None) -> None:
        self.enqueued.append((job_id, scheduled_at))


@pytest.mark.asyncio
async def test_create_post_passes_scheduled_at_into_create_flow():
    usecases = _StubPostUseCases()
    scheduler = _StubScheduler()
    media = [UploadFile(filename="photo.jpg", file=BytesIO(b"fake-jpeg-content"))]
    scheduled_at = "2026-05-01T12:00:00Z"

    response = await create_post(
        caption="scheduled launch",
        media=media,
        account_ids='["acc-1"]',
        scheduled_at=scheduled_at,
        media_type=None,
        thumbnail=None,
        igtv_title=None,
        usertags=None,
        location=None,
        extra_data=None,
        usecases=usecases,
        scheduler=scheduler,
    )

    assert usecases.create_request is not None
    assert usecases.create_request.scheduled_at == scheduled_at
    assert scheduler.enqueued == [("job-1", scheduled_at)]
    assert response["id"] == "job-1"
