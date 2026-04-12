"""Relationship routes for Instagram transport."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.adapters.instagram.error_utils import InstagramRateLimitError
from app.adapters.http.dependencies import get_relationship_usecases
from app.adapters.http.utils import format_error

from .mappers import _to_public_profile

router = APIRouter()


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
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Followers read failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Followers read failed")
        )


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
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Following read failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Following read failed")
        )


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
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Follower search failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Follower search failed")
        )


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
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Following search failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Following search failed")
        )


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
    except InstagramRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=format_error(
                exc, "Rate limited by Instagram. Please wait before trying again."
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Follow failed"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Follow failed"))


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
    except InstagramRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=format_error(
                exc, "Rate limited by Instagram. Please wait before trying again."
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Unfollow failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Unfollow failed")
        )


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
    except InstagramRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=format_error(
                exc, "Rate limited by Instagram. Please wait before trying again."
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Remove follower failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Remove follower failed")
        )


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
    except InstagramRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=format_error(
                exc, "Rate limited by Instagram. Please wait before trying again."
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Close friend add failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Close friend add failed")
        )


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
    except InstagramRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=format_error(
                exc, "Rate limited by Instagram. Please wait before trying again."
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Close friend remove failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Close friend remove failed")
        )


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
            yield f"data: {json.dumps(result)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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
            yield f"data: {json.dumps(result)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
