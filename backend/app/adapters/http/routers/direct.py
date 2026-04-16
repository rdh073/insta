"""Direct-message attachment endpoints (photo/video/voice uploads + media/story shares).

Distinct from the Instagram vertical router at /api/instagram/direct/*
— these routes are attachment-focused and speak multipart (file uploads)
or typed JSON bodies for sharing existing Instagram resources.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.adapters.http.dependencies import get_direct_usecases
from app.adapters.http.utils import format_instagram_http_error


router = APIRouter(prefix="/api/direct", tags=["direct"])


def _raise_instagram_error(exc: Exception, *, context: str) -> None:
    status_code, detail = format_instagram_http_error(exc, context=context)
    raise HTTPException(status_code=status_code, detail=detail)


def _parse_thread_ids(raw: list[str]) -> list[str]:
    """Flatten multipart thread_ids[] entries (accept repeated fields or comma-split)."""
    ids: list[str] = []
    for entry in raw:
        if entry is None:
            continue
        for piece in str(entry).split(","):
            piece = piece.strip()
            if piece:
                ids.append(piece)
    return ids


def _ack_to_dict(ack) -> dict:
    return {
        "threadIds": list(ack.thread_ids),
        "kind": ack.kind,
        "messageId": ack.message_id,
        "sentAt": ack.sent_at.isoformat() if ack.sent_at else None,
    }


async def _persist_upload(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix or ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await upload.read())
    finally:
        tmp.close()
    return tmp.name


class _ShareMediaEnvelope(BaseModel):
    thread_ids: list[str] = Field(..., description="Direct thread IDs (<=32)")
    media_id: str = Field(..., description="Instagram media id to share")


class _ShareStoryEnvelope(BaseModel):
    thread_ids: list[str] = Field(..., description="Direct thread IDs (<=32)")
    story_pk: int = Field(..., description="Instagram story PK to share")


@router.post("/{account_id}/send/photo")
async def send_photo(
    account_id: str,
    file: UploadFile = File(...),
    thread_ids: list[str] = Form(...),
    usecases=Depends(get_direct_usecases),
):
    """Send a photo attachment to one or more DM threads."""
    tids = _parse_thread_ids(thread_ids)
    tmp_path = await _persist_upload(file)
    try:
        ack = usecases.send_photo(account_id, tids, tmp_path)
        return _ack_to_dict(ack)
    except Exception as exc:
        _raise_instagram_error(exc, context="Send DM photo failed")


@router.post("/{account_id}/send/video")
async def send_video(
    account_id: str,
    file: UploadFile = File(...),
    thread_ids: list[str] = Form(...),
    usecases=Depends(get_direct_usecases),
):
    """Send a video attachment to one or more DM threads."""
    tids = _parse_thread_ids(thread_ids)
    tmp_path = await _persist_upload(file)
    try:
        ack = usecases.send_video(account_id, tids, tmp_path)
        return _ack_to_dict(ack)
    except Exception as exc:
        _raise_instagram_error(exc, context="Send DM video failed")


@router.post("/{account_id}/send/voice")
async def send_voice(
    account_id: str,
    file: UploadFile = File(...),
    thread_ids: list[str] = Form(...),
    usecases=Depends(get_direct_usecases),
):
    """Send a voice-note attachment to one or more DM threads."""
    tids = _parse_thread_ids(thread_ids)
    tmp_path = await _persist_upload(file)
    try:
        ack = usecases.send_voice(account_id, tids, tmp_path)
        return _ack_to_dict(ack)
    except Exception as exc:
        _raise_instagram_error(exc, context="Send DM voice failed")


@router.post("/{account_id}/share/media")
def share_media(
    account_id: str,
    body: _ShareMediaEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Share an existing Instagram post to one or more DM threads."""
    try:
        ack = usecases.share_media(account_id, body.thread_ids, body.media_id)
        return _ack_to_dict(ack)
    except Exception as exc:
        _raise_instagram_error(exc, context="Share DM media failed")


@router.post("/{account_id}/share/story")
def share_story(
    account_id: str,
    body: _ShareStoryEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Share an existing Instagram story to one or more DM threads."""
    try:
        ack = usecases.share_story(account_id, body.thread_ids, body.story_pk)
        return _ack_to_dict(ack)
    except Exception as exc:
        _raise_instagram_error(exc, context="Share DM story failed")
