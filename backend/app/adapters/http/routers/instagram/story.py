"""Story routes for Instagram transport."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.http.dependencies import get_story_usecases
from app.adapters.http.schemas.instagram import (
    StoryDeleteEnvelope,
    StoryMarkSeenEnvelope,
    StoryPublishEnvelope,
)
from app.adapters.http.utils import format_instagram_http_error
from app.application.dto.instagram_story_dto import StoryPublishRequest

from .mappers import _to_story_detail, _to_story_receipt, _to_story_summary

router = APIRouter()


def _raise_instagram_error(exc: Exception, *, context: str) -> None:
    status_code, detail = format_instagram_http_error(exc, context=context)
    raise HTTPException(status_code=status_code, detail=detail)


@router.get("/story/pk-from-url")
def get_story_pk_from_url(
    url: str = Query(..., description="Instagram story URL"),
    usecases=Depends(get_story_usecases),
):
    """Resolve story pk from URL via StoryUseCases."""
    try:
        story_pk = usecases.get_story_pk_from_url(url)
        return {"storyPk": story_pk}
    except Exception as exc:
        _raise_instagram_error(exc, context="Resolve story url failed")


@router.get("/story/{account_id}/{story_pk}")
def get_story(
    account_id: str,
    story_pk: int,
    use_cache: bool = Query(True, description="Use cached story metadata"),
    usecases=Depends(get_story_usecases),
):
    """Get story detail via StoryUseCases."""
    try:
        story = usecases.get_story(account_id, story_pk, use_cache=use_cache)
        return _to_story_detail(story)
    except Exception as exc:
        _raise_instagram_error(exc, context="Get story failed")


@router.get("/story/{account_id}/user/{user_id}")
def list_user_stories(
    account_id: str,
    user_id: int,
    amount: int | None = Query(None, ge=1, le=200),
    usecases=Depends(get_story_usecases),
):
    """List user stories via StoryUseCases."""
    try:
        stories = usecases.list_user_stories(account_id, user_id, amount=amount)
        return {"count": len(stories), "items": [_to_story_summary(s) for s in stories]}
    except Exception as exc:
        _raise_instagram_error(exc, context="List user stories failed")


@router.post("/story/publish")
def publish_story(
    body: StoryPublishEnvelope,
    usecases=Depends(get_story_usecases),
):
    """Publish story via StoryUseCases."""
    try:
        request = StoryPublishRequest(
            media_path=body.media_path,
            media_kind=body.media_kind,  # validated at use-case layer
            caption=body.caption or None,
            thumbnail_path=body.thumbnail_path,
            audience=body.audience,  # validated at use-case layer
        )
        story = usecases.publish_story(body.account_id, request)
        return _to_story_detail(story)
    except Exception as exc:
        _raise_instagram_error(exc, context="Publish story failed")


@router.post("/story/delete")
def delete_story(
    body: StoryDeleteEnvelope,
    usecases=Depends(get_story_usecases),
):
    """Delete story via StoryUseCases."""
    try:
        receipt = usecases.delete_story(body.account_id, body.story_pk)
        return _to_story_receipt(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Delete story failed")


@router.post("/story/mark-seen")
def mark_story_seen(
    body: StoryMarkSeenEnvelope,
    usecases=Depends(get_story_usecases),
):
    """Mark stories as seen via StoryUseCases."""
    try:
        receipt = usecases.mark_seen(
            body.account_id,
            story_pks=body.story_pks,
            skipped_story_pks=body.skipped_story_pks,
        )
        return _to_story_receipt(receipt)
    except Exception as exc:
        _raise_instagram_error(exc, context="Mark story seen failed")
