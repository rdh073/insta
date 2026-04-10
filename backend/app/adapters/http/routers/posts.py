"""Post job endpoints."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.adapters.http.dependencies import get_post_job_control, get_postjob_usecases, get_scheduler
from app.adapters.scheduler.event_bus import post_job_event_bus
from app.application.dto.post_dto import CreatePostJobRequest

router = APIRouter(prefix="/api/posts", tags=["posts"])


@router.get("")
def list_posts(usecases=Depends(get_postjob_usecases)):
    """List all post jobs."""
    posts = usecases.list_posts()
    return [
        {
            "id": post.id,
            "caption": post.caption,
            "status": post.status,
            "mediaType": post.media_type,
            "targets": post.targets,
            "results": post.results,
            "createdAt": post.created_at,
            "mediaUrls": post.media_urls,
        }
        for post in posts
    ]


@router.post("")
async def create_post(
    caption: str = Form(""),
    media: list[UploadFile] = File(...),
    account_ids: str = Form(...),
    scheduled_at: Optional[str] = Form(None),
    media_type: Optional[str] = Form(None),
    thumbnail: Optional[UploadFile] = File(None),
    igtv_title: Optional[str] = Form(None),
    usertags: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    extra_data: Optional[str] = Form(None),
    usecases=Depends(get_postjob_usecases),
    scheduler=Depends(get_scheduler),
):
    """Create a new post job and enqueue it for execution."""
    ids = json.loads(account_ids)

    media_paths = []
    for upload in media:
        suffix = Path(upload.filename or "file.jpg").suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(await upload.read())
        tmp.close()
        media_paths.append(tmp.name)

    thumbnail_path = None
    if thumbnail:
        suf = Path(thumbnail.filename or "thumb.jpg").suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suf)
        tmp.write(await thumbnail.read())
        tmp.close()
        thumbnail_path = tmp.name

    def _parse_json_form(value: Optional[str], field_name: str):
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail=f"Invalid JSON for '{field_name}'")

    request = CreatePostJobRequest(
        caption=caption,
        account_ids=ids,
        media_paths=media_paths,
        media_type=media_type or None,
        thumbnail_path=thumbnail_path,
        igtv_title=igtv_title or None,
        usertags=_parse_json_form(usertags, "usertags"),
        location=_parse_json_form(location, "location"),
        extra_data=_parse_json_form(extra_data, "extra_data"),
    )
    job_dto = usecases.create_post_job(request)

    # Enqueue onto the thread-safe job queue — no BackgroundTasks needed.
    scheduler.enqueue(job_dto.id, scheduled_at)

    return {
        "id": job_dto.id,
        "caption": job_dto.caption,
        "status": job_dto.status,
        "mediaType": job_dto.media_type,
        "targets": job_dto.targets,
        "results": job_dto.results,
        "createdAt": job_dto.created_at,
        "mediaUrls": job_dto.media_urls,
    }


def _get_job_or_404(job_id: str, control) -> dict:
    try:
        return control.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.delete("/{job_id}")
def delete_post_job(job_id: str, usecases=Depends(get_postjob_usecases)):
    """Delete a completed/failed/stopped job from the list."""
    try:
        usecases.delete_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    post_job_event_bus.notify("job_deleted")
    return {"deleted": job_id}


@router.post("/{job_id}/stop")
def stop_post_job(job_id: str, control=Depends(get_post_job_control)):
    """Stop a running or paused job after the current account finishes."""
    job = _get_job_or_404(job_id, control)
    if job["status"] not in ("running", "paused", "pending", "scheduled"):
        raise HTTPException(status_code=400, detail=f"Cannot stop job with status '{job['status']}'")
    control.request_stop(job_id)
    # Immediately mark terminal for jobs that aren't actively uploading.
    # Running jobs stay "running" until the executor finishes the current upload
    # and processes the stop flag — the executor's try/finally guarantees it will
    # reach a terminal status.
    if job["status"] in ("pending", "scheduled", "paused"):
        control.set_job_status(job_id, "stopped")
    post_job_event_bus.notify("job_stopped")
    return {"status": job["status"]}


@router.post("/{job_id}/pause")
def pause_post_job(job_id: str, control=Depends(get_post_job_control)):
    """Pause a running job between accounts."""
    job = _get_job_or_404(job_id, control)
    if job["status"] != "running":
        raise HTTPException(status_code=400, detail=f"Cannot pause job with status '{job['status']}'")
    control.request_pause(job_id)
    control.set_job_status(job_id, "paused")
    post_job_event_bus.notify("job_paused")
    return {"status": "paused"}


@router.post("/{job_id}/resume")
def resume_post_job(job_id: str, control=Depends(get_post_job_control)):
    """Resume a paused job."""
    job = _get_job_or_404(job_id, control)
    if job["status"] != "paused":
        raise HTTPException(status_code=400, detail=f"Cannot resume job with status '{job['status']}'")
    control.request_resume(job_id)
    control.set_job_status(job_id, "running")
    post_job_event_bus.notify("job_resumed")
    return {"status": "running"}


@router.get("/stream")
async def stream_post_jobs(usecases=Depends(get_postjob_usecases)):
    """SSE stream of post job updates.

    Emits the full job list whenever a job status changes, plus heartbeat every 15s.
    Clients connect once and receive push updates — no polling needed.
    """
    async def event_stream():
        listener_id, queue = post_job_event_bus.subscribe()
        try:
            # Send initial state immediately
            jobs = _serialize_jobs(usecases)
            yield f"data: {json.dumps(jobs)}\n\n"

            while True:
                try:
                    await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Heartbeat — keep connection alive
                    yield ": heartbeat\n\n"
                    continue

                jobs = _serialize_jobs(usecases)
                yield f"data: {json.dumps(jobs)}\n\n"
        finally:
            post_job_event_bus.unsubscribe(listener_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _serialize_jobs(usecases) -> list[dict]:
    return [
        {
            "id": post.id,
            "caption": post.caption,
            "status": post.status,
            "mediaType": post.media_type,
            "targets": post.targets,
            "results": post.results,
            "createdAt": post.created_at,
            "mediaUrls": post.media_urls,
        }
        for post in usecases.list_posts()
    ]
