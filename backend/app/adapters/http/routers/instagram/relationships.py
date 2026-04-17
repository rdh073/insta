"""Relationship routes for Instagram transport."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator

from app.adapters.http.dependencies import get_relationship_usecases
from app.adapters.http.streaming import sse_response
from app.adapters.http.utils import format_error, format_instagram_http_error

from .mappers import _to_public_profile

router = APIRouter()
logger = logging.getLogger(__name__)


def _raise_instagram_error(exc: Exception, *, context: str) -> None:
    status_code, detail = format_instagram_http_error(exc, context=context)
    raise HTTPException(status_code=status_code, detail=detail)


@router.get("/relationships/{account_id}/followers")
def list_followers(
    account_id: str,
    username: str = Query(..., description="Target username"),
    amount: int = Query(50, ge=1, le=200),
    usecases=Depends(get_relationship_usecases),
):
    """Read followers through RelationshipUseCases."""
    try:
        followers = usecases.list_followers(account_id, username, amount=amount)
        return [_to_public_profile(item) for item in followers]
    except Exception as exc:
        _raise_instagram_error(exc, context="Followers read failed")


@router.get("/relationships/{account_id}/following")
def list_following(
    account_id: str,
    username: str = Query(..., description="Target username"),
    amount: int = Query(50, ge=1, le=200),
    usecases=Depends(get_relationship_usecases),
):
    """Read following through RelationshipUseCases."""
    try:
        following = usecases.list_following(account_id, username, amount=amount)
        return [_to_public_profile(item) for item in following]
    except Exception as exc:
        _raise_instagram_error(exc, context="Following read failed")


@router.get("/relationships/{account_id}/followers/search")
def search_followers(
    account_id: str,
    username: str = Query(..., description="Target username whose followers to search"),
    query: str = Query(..., description="Search query string"),
    usecases=Depends(get_relationship_usecases),
):
    """Search within a user's follower list (server-side)."""
    try:
        results = usecases.search_followers(account_id, username, query=query)
        return [_to_public_profile(item) for item in results]
    except Exception as exc:
        _raise_instagram_error(exc, context="Follower search failed")


@router.get("/relationships/{account_id}/following/search")
def search_following(
    account_id: str,
    username: str = Query(..., description="Target username whose following to search"),
    query: str = Query(..., description="Search query string"),
    usecases=Depends(get_relationship_usecases),
):
    """Search within a user's following list (server-side)."""
    try:
        results = usecases.search_following(account_id, username, query=query)
        return [_to_public_profile(item) for item in results]
    except Exception as exc:
        _raise_instagram_error(exc, context="Following search failed")


@router.post("/relationships/{account_id}/follow")
def follow_user(
    account_id: str,
    target_username: str = Query(..., description="Username to follow"),
    usecases=Depends(get_relationship_usecases),
):
    """Follow a user by username."""
    try:
        success = usecases.follow_user(account_id, target_username)
        return {"success": success, "action": "follow", "target": target_username}
    except Exception as exc:
        _raise_instagram_error(exc, context="Follow failed")


@router.post("/relationships/{account_id}/unfollow")
def unfollow_user(
    account_id: str,
    target_username: str = Query(..., description="Username to unfollow"),
    usecases=Depends(get_relationship_usecases),
):
    """Unfollow a user by username."""
    try:
        success = usecases.unfollow_user(account_id, target_username)
        return {"success": success, "action": "unfollow", "target": target_username}
    except Exception as exc:
        _raise_instagram_error(exc, context="Unfollow failed")


@router.post("/relationships/{account_id}/remove-follower")
def remove_follower(
    account_id: str,
    target_username: str = Query(..., description="Follower username to remove"),
    usecases=Depends(get_relationship_usecases),
):
    """Remove a follower from the authenticated account."""
    try:
        success = usecases.remove_follower(account_id, target_username)
        return {
            "success": success,
            "action": "remove_follower",
            "target": target_username,
        }
    except Exception as exc:
        _raise_instagram_error(exc, context="Remove follower failed")


@router.post("/relationships/{account_id}/close-friends/add")
def close_friend_add(
    account_id: str,
    target_username: str = Query(..., description="Username to add to Close Friends"),
    usecases=Depends(get_relationship_usecases),
):
    """Add a user to the Close Friends list."""
    try:
        success = usecases.close_friend_add(account_id, target_username)
        return {
            "success": success,
            "action": "close_friend_add",
            "target": target_username,
        }
    except Exception as exc:
        _raise_instagram_error(exc, context="Close friend add failed")


@router.post("/relationships/{account_id}/close-friends/remove")
def close_friend_remove(
    account_id: str,
    target_username: str = Query(
        ..., description="Username to remove from Close Friends"
    ),
    usecases=Depends(get_relationship_usecases),
):
    """Remove a user from the Close Friends list."""
    try:
        success = usecases.close_friend_remove(account_id, target_username)
        return {
            "success": success,
            "action": "close_friend_remove",
            "target": target_username,
        }
    except Exception as exc:
        _raise_instagram_error(exc, context="Close friend remove failed")


# ---------------------------------------------------------------------------
# Mute + Notification toggles (single-user)
# ---------------------------------------------------------------------------


class _TargetPayload(BaseModel):
    """Body for per-user notification toggle endpoints."""

    target_username: str
    enabled: bool

    @field_validator("target_username")
    @classmethod
    def _require_username(cls, v: str) -> str:
        cleaned = (v or "").strip().lstrip("@")
        if not cleaned:
            raise ValueError("target_username is required")
        return cleaned


_NOTIFICATION_KINDS = ("posts", "videos", "reels", "stories")


@router.post("/relationships/{account_id}/mute-posts")
def mute_posts(
    account_id: str,
    target_username: str = Query(..., description="Username whose posts to mute"),
    usecases=Depends(get_relationship_usecases),
):
    """Mute feed posts from a followed user."""
    try:
        success = usecases.mute_posts(account_id, target_username)
        return {"success": success, "action": "mute_posts", "target": target_username}
    except Exception as exc:
        _raise_instagram_error(exc, context="Mute posts failed")


@router.post("/relationships/{account_id}/unmute-posts")
def unmute_posts(
    account_id: str,
    target_username: str = Query(..., description="Username whose posts to unmute"),
    usecases=Depends(get_relationship_usecases),
):
    """Unmute feed posts from a followed user."""
    try:
        success = usecases.unmute_posts(account_id, target_username)
        return {"success": success, "action": "unmute_posts", "target": target_username}
    except Exception as exc:
        _raise_instagram_error(exc, context="Unmute posts failed")


@router.post("/relationships/{account_id}/mute-stories")
def mute_stories(
    account_id: str,
    target_username: str = Query(..., description="Username whose stories to mute"),
    usecases=Depends(get_relationship_usecases),
):
    """Mute stories from a followed user."""
    try:
        success = usecases.mute_stories(account_id, target_username)
        return {"success": success, "action": "mute_stories", "target": target_username}
    except Exception as exc:
        _raise_instagram_error(exc, context="Mute stories failed")


@router.post("/relationships/{account_id}/unmute-stories")
def unmute_stories(
    account_id: str,
    target_username: str = Query(..., description="Username whose stories to unmute"),
    usecases=Depends(get_relationship_usecases),
):
    """Unmute stories from a followed user."""
    try:
        success = usecases.unmute_stories(account_id, target_username)
        return {
            "success": success,
            "action": "unmute_stories",
            "target": target_username,
        }
    except Exception as exc:
        _raise_instagram_error(exc, context="Unmute stories failed")


@router.post("/relationships/{account_id}/notifications/{kind}")
def set_user_notifications(
    account_id: str,
    kind: str,
    payload: _TargetPayload,
    usecases=Depends(get_relationship_usecases),
):
    """Toggle per-user push notifications for posts/videos/reels/stories."""
    if kind not in _NOTIFICATION_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"kind must be one of {list(_NOTIFICATION_KINDS)}",
        )
    try:
        success = usecases.set_user_notifications(
            account_id,
            payload.target_username,
            kind,
            payload.enabled,
        )
        return {
            "success": success,
            "action": f"{'enable' if payload.enabled else 'disable'}_{kind}_notifications",
            "target": payload.target_username,
            "enabled": payload.enabled,
        }
    except Exception as exc:
        _raise_instagram_error(exc, context="Toggle notifications failed")


# ---------------------------------------------------------------------------
# Batch Relationships (SSE)
# ---------------------------------------------------------------------------


class BatchRelationshipRequest(BaseModel):
    """Request payload for batch follow/unfollow."""

    account_ids: list[str]
    targets: list[str]
    concurrency: int = 3
    delay_between: float = 1.0

    @field_validator("account_ids")
    @classmethod
    def validate_account_ids(cls, v):
        if not v:
            raise ValueError("at least one account_id required")
        return list(dict.fromkeys(v))  # deduplicate

    @field_validator("targets")
    @classmethod
    def validate_targets(cls, v):
        cleaned = [t.strip().lstrip("@") for t in v if t.strip()]
        if not cleaned:
            raise ValueError("at least one target required")
        return list(dict.fromkeys(cleaned))

    @field_validator("concurrency")
    @classmethod
    def validate_concurrency(cls, v):
        return max(1, min(v, 10))

    @field_validator("delay_between")
    @classmethod
    def validate_delay(cls, v):
        return max(0.0, min(v, 10.0))


@router.post("/relationships/batch/follow")
async def batch_follow(
    request: BatchRelationshipRequest,
    usecases=Depends(get_relationship_usecases),
):
    """Batch follow targets from multiple accounts with SSE progress stream.

    Returns a Server-Sent Events stream. Each event is a JSON object with:
    - account, target, action, success, error (optional)
    - completed, total (progress counters)
    """

    async def event_stream():
        async for result in usecases.batch_follow(
            account_ids=request.account_ids,
            targets=request.targets,
            concurrency=request.concurrency,
            delay_between=request.delay_between,
        ):
            yield result

    def _batch_error(exc: Exception, _last_event) -> dict:
        return {
            "type": "run_error",
            "action": "follow",
            "message": format_error(exc, "Batch follow failed"),
        }

    return sse_response(
        event_stream(),
        logger=logger,
        include_done_sentinel=True,
        error_event_builder=_batch_error,
    )


@router.post("/relationships/batch/unfollow")
async def batch_unfollow(
    request: BatchRelationshipRequest,
    usecases=Depends(get_relationship_usecases),
):
    """Batch unfollow targets from multiple accounts with SSE progress stream."""

    async def event_stream():
        async for result in usecases.batch_unfollow(
            account_ids=request.account_ids,
            targets=request.targets,
            concurrency=request.concurrency,
            delay_between=request.delay_between,
        ):
            yield result

    def _batch_error(exc: Exception, _last_event) -> dict:
        return {
            "type": "run_error",
            "action": "unfollow",
            "message": format_error(exc, "Batch unfollow failed"),
        }

    return sse_response(
        event_stream(),
        logger=logger,
        include_done_sentinel=True,
        error_event_builder=_batch_error,
    )


# Ensure static batch routes are matched before dynamic /relationships/{account_id}/...
router.routes.sort(
    key=lambda route: 0 if "/relationships/batch/" in getattr(route, "path", "") else 1,
)
