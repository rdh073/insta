"""Insight routes for Instagram transport."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.http.dependencies import get_insight_usecases
from app.adapters.http.utils import format_error

from .mappers import _to_insight

router = APIRouter()


@router.get("/insight/{account_id}/media/{media_pk}")
def get_media_insight(
    account_id: str,
    media_pk: int,
    usecases=Depends(get_insight_usecases),
):
    """Get insight for a specific media item via InsightUseCases."""
    try:
        insight = usecases.get_media_insight(account_id, media_pk)
        return _to_insight(insight)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Media insight failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Media insight failed")
        )


@router.get("/insight/{account_id}/list")
def list_media_insights(
    account_id: str,
    post_type: str = Query("ALL", description="ALL | PHOTO | VIDEO | CAROUSEL"),
    time_frame: str = Query(
        "TWO_YEARS", description="TWO_YEARS | ONE_YEAR | SIX_MONTHS | MONTH | WEEK"
    ),
    ordering: str = Query(
        "REACH_COUNT",
        description="REACH_COUNT | IMPRESSIONS | ENGAGEMENT | LIKE_COUNT | ...",
    ),
    count: int = Query(0, ge=0),
    usecases=Depends(get_insight_usecases),
):
    """List post insights with filtering and ordering via InsightUseCases."""
    try:
        insights = usecases.list_media_insights(
            account_id,
            post_type=post_type,
            time_frame=time_frame,
            ordering=ordering,
            count=count,
        )
        return {"count": len(insights), "items": [_to_insight(i) for i in insights]}
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List insights failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List insights failed")
        )
