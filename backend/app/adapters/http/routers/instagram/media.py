"""Media routes for Instagram transport."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.http.dependencies import get_media_usecases
from app.adapters.http.schemas.instagram import (
    MediaActionEnvelope,
    MediaEditEnvelope,
    MediaSaveEnvelope,
)
from app.adapters.http.utils import format_instagram_http_error

from .mappers import _to_media, _to_media_receipt, _to_oembed

router = APIRouter()


def _raise_instagram_error(exc: Exception, *, context: str) -> None:
    status_code, detail = format_instagram_http_error(exc, context=context)
    raise HTTPException(status_code=status_code, detail=detail)


@router.get("/media/{account_id}/pk/{media_pk}")
def get_media_by_pk(
    account_id: str,
    media_pk: int,
    usecases=Depends(get_media_usecases),
):
    """Get media by pk through MediaUseCases."""
    try:
        media = usecases.get_media_by_pk(account_id, media_pk)
        return _to_media(media)
    except Exception as exc:
        status_code, detail = format_instagram_http_error(
            exc, context="Get media by pk failed"
        )
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/media/{account_id}/code/{code}")
def get_media_by_code(
    account_id: str,
    code: str,
    usecases=Depends(get_media_usecases),
):
    """Get media by code through MediaUseCases."""
    try:
        media = usecases.get_media_by_code(account_id, code)
        return _to_media(media)
    except Exception as exc:
        status_code, detail = format_instagram_http_error(
            exc, context="Get media by code failed"
        )
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/media/{account_id}/user/{user_id}")
def get_user_medias(
    account_id: str,
    user_id: int,
    amount: int = Query(12, ge=1, le=200),
    usecases=Depends(get_media_usecases),
):
    """Get user medias through MediaUseCases."""
    try:
        medias = usecases.get_user_medias(account_id, user_id, amount=amount)
        return {"count": len(medias), "posts": [_to_media(m) for m in medias]}
    except Exception as exc:
        status_code, detail = format_instagram_http_error(
            exc, context="Get user medias failed"
        )
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/media/{account_id}/oembed")
def get_media_oembed(
    account_id: str,
    url: str = Query(..., description="Instagram post/reel URL"),
    usecases=Depends(get_media_usecases),
):
    """Get media oEmbed metadata through MediaUseCases."""
    try:
        oembed = usecases.get_media_oembed(account_id, url)
        return _to_oembed(oembed)
    except Exception as exc:
        status_code, detail = format_instagram_http_error(
            exc, context="Get media oembed failed"
        )
        raise HTTPException(status_code=status_code, detail=detail)


@router.post("/media/edit")
def edit_media_caption(
    body: MediaEditEnvelope,
    usecases=Depends(get_media_usecases),
):
    """Edit a published post's caption."""
    try:
        receipt = usecases.edit_caption(body.account_id, body.media_id, body.caption)
        return _to_media_receipt(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Edit media caption failed")


@router.post("/media/delete")
def delete_media(
    body: MediaActionEnvelope,
    usecases=Depends(get_media_usecases),
):
    """Permanently delete a post."""
    try:
        receipt = usecases.delete_media(body.account_id, body.media_id)
        return _to_media_receipt(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Delete media failed")


@router.post("/media/pin")
def pin_media(
    body: MediaActionEnvelope,
    usecases=Depends(get_media_usecases),
):
    """Pin a post to the profile grid."""
    try:
        receipt = usecases.pin_media(body.account_id, body.media_id)
        return _to_media_receipt(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Pin media failed")


@router.post("/media/unpin")
def unpin_media(
    body: MediaActionEnvelope,
    usecases=Depends(get_media_usecases),
):
    """Unpin a previously pinned post."""
    try:
        receipt = usecases.unpin_media(body.account_id, body.media_id)
        return _to_media_receipt(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Unpin media failed")


@router.post("/media/archive")
def archive_media(
    body: MediaActionEnvelope,
    usecases=Depends(get_media_usecases),
):
    """Archive a post (hidden from public profile)."""
    try:
        receipt = usecases.archive_media(body.account_id, body.media_id)
        return _to_media_receipt(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Archive media failed")


@router.post("/media/unarchive")
def unarchive_media(
    body: MediaActionEnvelope,
    usecases=Depends(get_media_usecases),
):
    """Restore an archived post to the public profile."""
    try:
        receipt = usecases.unarchive_media(body.account_id, body.media_id)
        return _to_media_receipt(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Unarchive media failed")


@router.post("/media/save")
def save_media(
    body: MediaSaveEnvelope,
    usecases=Depends(get_media_usecases),
):
    """Bookmark a post into a saved collection (optional collection target)."""
    try:
        receipt = usecases.save_media(
            body.account_id, body.media_id, body.collection_pk
        )
        return _to_media_receipt(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Save media failed")


@router.post("/media/unsave")
def unsave_media(
    body: MediaSaveEnvelope,
    usecases=Depends(get_media_usecases),
):
    """Remove a post from a saved collection."""
    try:
        receipt = usecases.unsave_media(
            body.account_id, body.media_id, body.collection_pk
        )
        return _to_media_receipt(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Unsave media failed")
