"""Highlight routes for Instagram transport."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.http.dependencies import get_highlight_usecases
from app.adapters.http.schemas.instagram import (
    HighlightChangeTitleEnvelope,
    HighlightCreateEnvelope,
    HighlightDeleteEnvelope,
    HighlightStoriesEnvelope,
)
from app.adapters.http.utils import format_error

from .mappers import _to_highlight_detail, _to_highlight_receipt, _to_highlight_summary

router = APIRouter()


@router.get("/highlight/pk-from-url")
def get_highlight_pk_from_url(
    url: str = Query(..., description="Instagram highlight URL"),
    usecases=Depends(get_highlight_usecases),
):
    """Resolve highlight pk from URL via HighlightUseCases."""
    try:
        highlight_pk = usecases.get_highlight_pk_from_url(url)
        return {"highlightPk": highlight_pk}
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Resolve highlight url failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Resolve highlight url failed")
        )


@router.get("/highlight/{account_id}/{highlight_pk}")
def get_highlight(
    account_id: str,
    highlight_pk: int,
    usecases=Depends(get_highlight_usecases),
):
    """Get highlight detail via HighlightUseCases."""
    try:
        highlight = usecases.get_highlight(account_id, highlight_pk)
        return _to_highlight_detail(highlight)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get highlight failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get highlight failed")
        )


@router.get("/highlight/{account_id}/user/{user_id}")
def list_user_highlights(
    account_id: str,
    user_id: int,
    amount: int = Query(0, ge=0, le=200),
    usecases=Depends(get_highlight_usecases),
):
    """List user highlights via HighlightUseCases."""
    try:
        highlights = usecases.list_user_highlights(account_id, user_id, amount=amount)
        return {
            "count": len(highlights),
            "items": [_to_highlight_summary(h) for h in highlights],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List highlights failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List highlights failed")
        )


@router.post("/highlight/create")
def create_highlight(
    body: HighlightCreateEnvelope,
    usecases=Depends(get_highlight_usecases),
):
    """Create highlight via HighlightUseCases."""
    try:
        highlight = usecases.create_highlight(
            body.account_id,
            title=body.title,
            story_ids=body.story_ids,
            cover_story_id=body.cover_story_id,
            crop_rect=body.crop_rect,
        )
        return _to_highlight_detail(highlight)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Create highlight failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Create highlight failed")
        )


@router.post("/highlight/change-title")
def change_highlight_title(
    body: HighlightChangeTitleEnvelope,
    usecases=Depends(get_highlight_usecases),
):
    """Change highlight title via HighlightUseCases."""
    try:
        highlight = usecases.change_title(
            body.account_id, body.highlight_pk, body.title
        )
        return _to_highlight_detail(highlight)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Change highlight title failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Change highlight title failed")
        )


@router.post("/highlight/add-stories")
def add_highlight_stories(
    body: HighlightStoriesEnvelope,
    usecases=Depends(get_highlight_usecases),
):
    """Add stories to highlight via HighlightUseCases."""
    try:
        highlight = usecases.add_stories(
            body.account_id, body.highlight_pk, body.story_ids
        )
        return _to_highlight_detail(highlight)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Add highlight stories failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Add highlight stories failed")
        )


@router.post("/highlight/remove-stories")
def remove_highlight_stories(
    body: HighlightStoriesEnvelope,
    usecases=Depends(get_highlight_usecases),
):
    """Remove stories from highlight via HighlightUseCases."""
    try:
        highlight = usecases.remove_stories(
            body.account_id, body.highlight_pk, body.story_ids
        )
        return _to_highlight_detail(highlight)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Remove highlight stories failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Remove highlight stories failed")
        )


@router.post("/highlight/delete")
def delete_highlight(
    body: HighlightDeleteEnvelope,
    usecases=Depends(get_highlight_usecases),
):
    """Delete highlight via HighlightUseCases."""
    try:
        receipt = usecases.delete_highlight(body.account_id, body.highlight_pk)
        return _to_highlight_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Delete highlight failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Delete highlight failed")
        )
