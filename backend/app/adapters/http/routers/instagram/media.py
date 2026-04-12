"""Media routes for Instagram transport."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.http.dependencies import get_media_usecases
from app.adapters.http.utils import format_error

from .mappers import _to_media, _to_oembed

router = APIRouter()


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
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get media by pk failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get media by pk failed")
        )


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
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get media by code failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get media by code failed")
        )


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
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get user medias failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get user medias failed")
        )


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
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get media oembed failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get media oembed failed")
        )
