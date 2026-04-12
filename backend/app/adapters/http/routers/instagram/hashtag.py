"""Hashtag routes for Instagram transport."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.http.dependencies import get_hashtag_usecases
from app.adapters.http.utils import format_error

from .mappers import _to_media

router = APIRouter()


@router.get("/hashtag/{account_id}/search")
def search_hashtags(
    account_id: str,
    q: str = Query(..., description="Search query (with or without #)"),
    usecases=Depends(get_hashtag_usecases),
):
    """Search hashtags by query string via HashtagUseCases."""
    try:
        results = usecases.search_hashtags(account_id, q)
        return [
            {
                "id": ht.id,
                "name": ht.name,
                "mediaCount": ht.media_count,
            }
            for ht in results
        ]
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Search hashtags failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Search hashtags failed")
        )


@router.get("/hashtag/{account_id}")
def get_hashtag(
    account_id: str,
    name: str = Query(..., description="Hashtag name (with or without #)"),
    usecases=Depends(get_hashtag_usecases),
):
    """Fetch hashtag metadata via HashtagUseCases."""
    try:
        hashtag = usecases.get_hashtag(account_id, name)
        return {
            "id": hashtag.id,
            "name": hashtag.name,
            "mediaCount": hashtag.media_count,
            "profilePicUrl": hashtag.profile_pic_url,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get hashtag failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get hashtag failed")
        )


@router.get("/hashtag/{account_id}/top-posts")
def get_hashtag_top_posts(
    account_id: str,
    name: str = Query(..., description="Hashtag name (with or without #)"),
    amount: int = Query(12, ge=1, le=200),
    usecases=Depends(get_hashtag_usecases),
):
    """Fetch top posts for a hashtag via HashtagUseCases."""
    try:
        medias = usecases.get_hashtag_top_posts(account_id, name, amount=amount)
        return {
            "hashtag": name,
            "feed": "top",
            "count": len(medias),
            "posts": [_to_media(m) for m in medias],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Hashtag top posts failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Hashtag top posts failed")
        )


@router.get("/hashtag/{account_id}/recent-posts")
def get_hashtag_recent_posts(
    account_id: str,
    name: str = Query(..., description="Hashtag name (with or without #)"),
    amount: int = Query(12, ge=1, le=200),
    usecases=Depends(get_hashtag_usecases),
):
    """Fetch recent posts for a hashtag via HashtagUseCases."""
    try:
        medias = usecases.get_hashtag_recent_posts(account_id, name, amount=amount)
        return {
            "hashtag": name,
            "feed": "recent",
            "count": len(medias),
            "posts": [_to_media(m) for m in medias],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Hashtag recent posts failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Hashtag recent posts failed")
        )
