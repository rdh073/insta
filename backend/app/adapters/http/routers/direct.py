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


class _ThreadActionEnvelope(BaseModel):
    account_id: str = Field(..., description="Application account ID")


class _HideThreadEnvelope(_ThreadActionEnvelope):
    move_to_spam: bool = Field(
        default=False,
        description="If true, move thread to the hidden/spam folder instead of just hiding",
    )


class _ShareProfileEnvelope(BaseModel):
    account_id: str = Field(..., description="Application account ID")
    thread_ids: list[str] = Field(..., description="Direct thread IDs (<=32)")
    user_id: int = Field(..., description="Instagram user id (pk) of the profile to share")


def _receipt_to_dict(receipt) -> dict:
    return {
        "actionId": receipt.action_id,
        "success": receipt.success,
        "reason": receipt.reason,
    }


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


# ---------------------------------------------------------------------------
# Thread management (mute / unmute / hide / mark-unread / profile-share)
# ---------------------------------------------------------------------------


@router.post("/{thread_id}/mute")
def mute_thread(
    thread_id: str,
    body: _ThreadActionEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Mute notifications for a thread."""
    try:
        receipt = usecases.mute_thread(body.account_id, thread_id)
        return _receipt_to_dict(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Mute thread failed")


@router.post("/{thread_id}/unmute")
def unmute_thread(
    thread_id: str,
    body: _ThreadActionEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Unmute notifications for a thread."""
    try:
        receipt = usecases.unmute_thread(body.account_id, thread_id)
        return _receipt_to_dict(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Unmute thread failed")


@router.post("/{thread_id}/hide")
def hide_thread(
    thread_id: str,
    body: _HideThreadEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Hide a thread from the inbox (Instagram's "delete thread" behaviour)."""
    try:
        receipt = usecases.hide_thread(
            body.account_id, thread_id, move_to_spam=body.move_to_spam
        )
        return _receipt_to_dict(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Hide thread failed")


@router.post("/{thread_id}/mark-unread")
def mark_thread_unread(
    thread_id: str,
    body: _ThreadActionEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Mark a thread as unread so it surfaces for follow-up."""
    try:
        receipt = usecases.mark_thread_unread(body.account_id, thread_id)
        return _receipt_to_dict(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Mark thread unread failed")


@router.post("/share-profile")
def share_profile(
    body: _ShareProfileEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Share a user profile to one or more DM threads."""
    try:
        ack = usecases.share_profile(body.account_id, body.thread_ids, body.user_id)
        return _ack_to_dict(ack)
    except Exception as exc:
        _raise_instagram_error(exc, context="Share profile failed")
