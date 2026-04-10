"""Instagram vertical router — thin transport layer over application use cases.

Phase 9: all vertical routes delegate to use cases. No adapter dependency is allowed here.
Validation is owned by use cases; the router only translates HTTP ↔ DTO and maps errors.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.adapters.instagram.error_utils import InstagramRateLimitError
from app.adapters.http.dependencies import (
    get_identity_usecases,
    get_relationship_usecases,
    get_media_usecases,
    get_story_usecases,
    get_hashtag_usecases,
    get_highlight_usecases,
    get_collection_usecases,
    get_insight_usecases,
    get_comment_usecases,
    get_direct_usecases,
)
from app.adapters.http.schemas.instagram import (
    StoryPublishEnvelope,
    StoryDeleteEnvelope,
    StoryMarkSeenEnvelope,
    HighlightCreateEnvelope,
    HighlightChangeTitleEnvelope,
    HighlightStoriesEnvelope,
    HighlightDeleteEnvelope,
    CommentCreateEnvelope,
    CommentDeleteEnvelope,
    CommentLikeEnvelope,
    CommentPinEnvelope,
    DirectSendEnvelope,
    DirectFindOrCreateEnvelope,
    DirectSendThreadEnvelope,
    DirectSendUsersEnvelope,
    DirectDeleteMessageEnvelope,
    DirectThreadActionEnvelope,
)
from app.adapters.http.utils import format_error
from app.application.dto.instagram_story_dto import StoryPublishRequest

router = APIRouter(prefix="/api/instagram", tags=["instagram"])


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


@router.get("/capabilities")
def get_instagram_capabilities():
    """Expose vertical ownership contract for Instagram transport."""
    return {
        "owner": "application_usecases",
        "verticals": [
            "media",
            "story",
            "comment",
            "direct",
            "hashtag",
            "highlight",
            "collection",
            "insight",
        ],
        "phase": 9,
    }


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


@router.get("/identity/{account_id}/me")
def get_authenticated_identity(
    account_id: str, usecases=Depends(get_identity_usecases)
):
    """Read authenticated account profile through IdentityUseCases."""
    try:
        profile = usecases.get_authenticated_account(account_id)
        return {
            "pk": profile.pk,
            "username": profile.username,
            "fullName": profile.full_name,
            "biography": profile.biography,
            "profilePicUrl": profile.profile_pic_url,
            "externalUrl": profile.external_url,
            "isPrivate": profile.is_private,
            "isVerified": profile.is_verified,
            "isBusiness": profile.is_business,
            "email": profile.email,
            "phoneNumber": profile.phone_number,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail=format_error(exc, "Account not found")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Identity read failed")
        )


@router.get("/identity/{account_id}/user/{username}")
def get_public_user_by_username(
    account_id: str,
    username: str,
    usecases=Depends(get_identity_usecases),
):
    """Resolve a public Instagram username to its numeric user ID and profile."""
    try:
        profile = usecases.get_public_user_by_username(account_id, username)
        return _to_public_profile(profile)
    except InstagramRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=format_error(
                exc, "Rate limited by Instagram. Please wait before trying again."
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=format_error(exc, "User not found"))
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "User lookup failed")
        )


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Story
# ---------------------------------------------------------------------------


@router.get("/story/pk-from-url")
def get_story_pk_from_url(
    url: str = Query(..., description="Instagram story URL"),
    usecases=Depends(get_story_usecases),
):
    """Resolve story pk from URL via StoryUseCases."""
    try:
        story_pk = usecases.get_story_pk_from_url(url)
        return {"storyPk": story_pk}
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Resolve story url failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Resolve story url failed")
        )


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
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get story failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get story failed")
        )


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
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List user stories failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List user stories failed")
        )


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
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Publish story failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Publish story failed")
        )


@router.post("/story/delete")
def delete_story(
    body: StoryDeleteEnvelope,
    usecases=Depends(get_story_usecases),
):
    """Delete story via StoryUseCases."""
    try:
        receipt = usecases.delete_story(body.account_id, body.story_pk)
        return _to_story_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Delete story failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Delete story failed")
        )


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
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Mark story seen failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Mark story seen failed")
        )


# ---------------------------------------------------------------------------
# Hashtag
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Highlight
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


@router.get("/collection/{account_id}")
def list_collections(
    account_id: str,
    usecases=Depends(get_collection_usecases),
):
    """List all saved collections for an account via CollectionUseCases."""
    try:
        collections = usecases.list_collections(account_id)
        return [
            {
                "pk": c.pk,
                "name": c.name,
                "type": c.collection_type,
                "mediaCount": c.media_count,
            }
            for c in collections
        ]
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List collections failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List collections failed")
        )


@router.get("/collection/{account_id}/posts")
def get_collection_posts(
    account_id: str,
    name: str = Query(..., description="Collection name"),
    amount: int = Query(21, ge=1, le=200),
    last_media_pk: int = Query(0, ge=0),
    usecases=Depends(get_collection_usecases),
):
    """Get posts in a named collection via CollectionUseCases."""
    try:
        collection_pk = usecases.get_collection_pk_by_name(account_id, name)
        posts = usecases.get_collection_posts(
            account_id, collection_pk, amount=amount, last_media_pk=last_media_pk
        )
        return {
            "collection": name,
            "count": len(posts),
            "posts": [_to_media(m) for m in posts],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Collection posts failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Collection posts failed")
        )


# ---------------------------------------------------------------------------
# Insight
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------


@router.post("/comment")
def create_comment(
    body: CommentCreateEnvelope,
    usecases=Depends(get_comment_usecases),
):
    """Create a comment or reply via CommentUseCases."""
    try:
        comment = usecases.create_comment(
            body.account_id,
            body.media_id,
            body.text,
            reply_to_comment_id=body.reply_to_comment_id,
        )
        return {
            "pk": comment.pk,
            "text": comment.text,
            "author": comment.author.username,
            "createdAt": comment.created_at.isoformat() if comment.created_at else None,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Create comment failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Create comment failed")
        )


@router.get("/comment/{account_id}/{media_id}")
def list_comments(
    account_id: str,
    media_id: str,
    amount: int = Query(0, ge=0),
    usecases=Depends(get_comment_usecases),
):
    """List comments for a media item via CommentUseCases."""
    try:
        comments = usecases.list_comments(account_id, media_id, amount=amount)
        return {
            "count": len(comments),
            "comments": [
                {
                    "pk": c.pk,
                    "text": c.text,
                    "author": c.author.username,
                    "likeCount": c.like_count,
                    "createdAt": c.created_at.isoformat() if c.created_at else None,
                }
                for c in comments
            ],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List comments failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List comments failed")
        )


@router.get("/comment/{account_id}/{media_id}/page")
def list_comments_page(
    account_id: str,
    media_id: str,
    page_size: int = Query(20, ge=1, le=200),
    cursor: str | None = Query(None),
    usecases=Depends(get_comment_usecases),
):
    """List comments page for a media item via CommentUseCases."""
    try:
        page = usecases.list_comments_page(
            account_id=account_id,
            media_id=media_id,
            page_size=page_size,
            cursor=cursor,
        )
        return {
            "count": len(page.comments),
            "nextCursor": page.next_cursor,
            "comments": [_to_comment(c) for c in page.comments],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List comments page failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List comments page failed")
        )


@router.post("/comment/delete")
def delete_comment(
    body: CommentDeleteEnvelope,
    usecases=Depends(get_comment_usecases),
):
    """Delete a comment via CommentUseCases."""
    try:
        receipt = usecases.delete_comment(
            account_id=body.account_id,
            media_id=body.media_id,
            comment_id=body.comment_id,
        )
        return _to_comment_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Delete comment failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Delete comment failed")
        )


@router.post("/comment/like")
def like_comment(
    body: CommentLikeEnvelope,
    usecases=Depends(get_comment_usecases),
):
    """Like a comment."""
    try:
        receipt = usecases.like_comment(account_id=body.account_id, comment_id=body.comment_id)
        return _to_comment_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Like comment failed"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Like comment failed"))


@router.post("/comment/unlike")
def unlike_comment(
    body: CommentLikeEnvelope,
    usecases=Depends(get_comment_usecases),
):
    """Unlike a comment."""
    try:
        receipt = usecases.unlike_comment(account_id=body.account_id, comment_id=body.comment_id)
        return _to_comment_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Unlike comment failed"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Unlike comment failed"))


@router.post("/comment/pin")
def pin_comment(
    body: CommentPinEnvelope,
    usecases=Depends(get_comment_usecases),
):
    """Pin a comment on a post owned by the account."""
    try:
        receipt = usecases.pin_comment(
            account_id=body.account_id, media_id=body.media_id, comment_id=body.comment_id
        )
        return _to_comment_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Pin comment failed"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Pin comment failed"))


@router.post("/comment/unpin")
def unpin_comment(
    body: CommentPinEnvelope,
    usecases=Depends(get_comment_usecases),
):
    """Unpin a comment on a post owned by the account."""
    try:
        receipt = usecases.unpin_comment(
            account_id=body.account_id, media_id=body.media_id, comment_id=body.comment_id
        )
        return _to_comment_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Unpin comment failed"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Unpin comment failed"))


# ---------------------------------------------------------------------------
# Direct
# ---------------------------------------------------------------------------


@router.post("/direct/send")
def send_direct_message(
    body: DirectSendEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Send a DM to a user by username via DirectUseCases."""
    try:
        message = usecases.send_to_username(body.account_id, body.username, body.text)
        return {
            "directMessageId": message.direct_message_id,
            "directThreadId": message.direct_thread_id,
            "text": message.text,
            "sentAt": message.sent_at.isoformat() if message.sent_at else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Send DM failed"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Send DM failed"))


@router.post("/direct/find-or-create")
def find_or_create_direct_thread(
    body: DirectFindOrCreateEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Find or create a direct thread via DirectUseCases."""
    try:
        thread = usecases.find_or_create_thread(
            account_id=body.account_id,
            participant_user_ids=body.participant_user_ids,
        )
        return _to_direct_thread_summary(thread)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Find/create thread failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Find/create thread failed")
        )


@router.post("/direct/send-thread")
def send_direct_to_thread(
    body: DirectSendThreadEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Send DM to an existing thread via DirectUseCases."""
    try:
        message = usecases.send_to_thread(
            account_id=body.account_id,
            direct_thread_id=body.direct_thread_id,
            text=body.text,
        )
        return _to_direct_message(message)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Send to thread failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Send to thread failed")
        )


@router.post("/direct/send-users")
def send_direct_to_users(
    body: DirectSendUsersEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Send DM to users via DirectUseCases."""
    try:
        message = usecases.send_to_users(
            account_id=body.account_id,
            user_ids=body.user_ids,
            text=body.text,
        )
        return _to_direct_message(message)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Send to users failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Send to users failed")
        )


@router.post("/direct/delete-message")
def delete_direct_message(
    body: DirectDeleteMessageEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Delete a DM message via DirectUseCases."""
    try:
        receipt = usecases.delete_message(
            account_id=body.account_id,
            direct_thread_id=body.direct_thread_id,
            direct_message_id=body.direct_message_id,
        )
        return _to_direct_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Delete DM failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Delete DM failed")
        )


@router.post("/direct/approve-pending")
def approve_pending_direct_thread(
    body: DirectThreadActionEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Approve a pending DM request, moving it to the main inbox."""
    try:
        receipt = usecases.approve_pending_thread(
            account_id=body.account_id,
            direct_thread_id=body.direct_thread_id,
        )
        return _to_direct_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Approve pending thread failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Approve pending thread failed")
        )


@router.post("/direct/mark-seen")
def mark_direct_thread_seen(
    body: DirectThreadActionEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Mark the most recent message in a thread as seen."""
    try:
        receipt = usecases.mark_thread_seen(
            account_id=body.account_id,
            direct_thread_id=body.direct_thread_id,
        )
        return _to_direct_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Mark thread seen failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Mark thread seen failed")
        )


@router.get("/direct/{account_id}/inbox")
def list_inbox(
    account_id: str,
    amount: int = Query(20, ge=1, le=100),
    usecases=Depends(get_direct_usecases),
):
    """List inbox threads via DirectUseCases."""
    try:
        threads = usecases.list_inbox_threads(account_id, amount=amount)
        return {
            "count": len(threads),
            "threads": [
                {
                    "directThreadId": t.direct_thread_id,
                    "participants": [p.username for p in t.participants],
                    "isPending": t.is_pending,
                    "lastMessage": t.last_message.text if t.last_message else None,
                }
                for t in threads
            ],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List inbox failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List inbox failed")
        )


@router.get("/direct/{account_id}/pending")
def list_pending_inbox(
    account_id: str,
    amount: int = Query(20, ge=1, le=100),
    usecases=Depends(get_direct_usecases),
):
    """List pending DM threads via DirectUseCases."""
    try:
        threads = usecases.list_pending_threads(account_id, amount=amount)
        return {
            "count": len(threads),
            "threads": [_to_direct_thread_summary(t) for t in threads],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List pending inbox failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List pending inbox failed")
        )


@router.get("/direct/{account_id}/thread/{direct_thread_id}")
def get_direct_thread(
    account_id: str,
    direct_thread_id: str,
    amount: int = Query(20, ge=1, le=200),
    usecases=Depends(get_direct_usecases),
):
    """Get a direct thread with messages via DirectUseCases."""
    try:
        thread = usecases.get_thread(account_id, direct_thread_id, amount=amount)
        return _to_direct_thread_detail(thread)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get direct thread failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get direct thread failed")
        )


@router.get("/direct/{account_id}/thread/{direct_thread_id}/messages")
def list_direct_messages(
    account_id: str,
    direct_thread_id: str,
    amount: int = Query(20, ge=1, le=200),
    usecases=Depends(get_direct_usecases),
):
    """List direct messages in thread via DirectUseCases."""
    try:
        messages = usecases.list_messages(account_id, direct_thread_id, amount=amount)
        return {
            "count": len(messages),
            "messages": [_to_direct_message(m) for m in messages],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List direct messages failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List direct messages failed")
        )


@router.get("/direct/{account_id}/search")
def search_direct_threads(
    account_id: str,
    query: str = Query(..., description="Search query"),
    usecases=Depends(get_direct_usecases),
):
    """Search direct threads via DirectUseCases."""
    try:
        threads = usecases.search_threads(account_id, query)
        return {
            "count": len(threads),
            "threads": [_to_direct_thread_summary(t) for t in threads],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Search direct threads failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Search direct threads failed")
        )


# ---------------------------------------------------------------------------
# Shared DTO mappers
# ---------------------------------------------------------------------------


def _to_public_profile(item) -> dict:
    return {
        "pk": item.pk,
        "username": item.username,
        "fullName": item.full_name,
        "biography": item.biography,
        "profilePicUrl": item.profile_pic_url,
        "followerCount": item.follower_count,
        "followingCount": item.following_count,
        "mediaCount": item.media_count,
        "isPrivate": item.is_private,
        "isVerified": item.is_verified,
        "isBusiness": item.is_business,
    }


def _to_media(m) -> dict:
    return {
        "pk": m.pk,
        "mediaId": m.media_id,
        "code": m.code,
        "owner": m.owner_username,
        "captionText": m.caption_text,
        "likeCount": m.like_count,
        "commentCount": m.comment_count,
        "mediaType": m.media_type,
        "productType": m.product_type,
        "takenAt": m.taken_at.isoformat() if m.taken_at else None,
        "resources": [_to_resource(r) for r in m.resources],
    }


def _to_resource(r) -> dict:
    return {
        "pk": r.pk,
        "mediaType": r.media_type,
        "thumbnailUrl": r.thumbnail_url,
        "videoUrl": r.video_url,
    }


def _to_oembed(o) -> dict:
    return {
        "mediaId": o.media_id,
        "authorName": o.author_name,
        "authorUrl": o.author_url,
        "authorId": o.author_id,
        "title": o.title,
        "providerName": o.provider_name,
        "html": o.html,
        "thumbnailUrl": o.thumbnail_url,
        "width": o.width,
        "height": o.height,
        "canView": o.can_view,
    }


def _to_story_summary(s) -> dict:
    return {
        "pk": s.pk,
        "storyId": s.story_id,
        "mediaType": s.media_type,
        "takenAt": s.taken_at.isoformat() if s.taken_at else None,
        "thumbnailUrl": s.thumbnail_url,
        "videoUrl": s.video_url,
        "viewerCount": s.viewer_count,
        "ownerUsername": s.owner_username,
    }


def _to_story_detail(s) -> dict:
    return {
        "summary": _to_story_summary(s.summary),
        "linkCount": s.link_count,
        "mentionCount": s.mention_count,
        "hashtagCount": s.hashtag_count,
        "locationCount": s.location_count,
        "stickerCount": s.sticker_count,
    }


def _to_story_receipt(r) -> dict:
    return {
        "actionId": r.action_id,
        "success": r.success,
        "reason": r.reason,
    }


def _to_comment(c) -> dict:
    return {
        "pk": c.pk,
        "text": c.text,
        "author": c.author.username,
        "likeCount": c.like_count,
        "hasLiked": c.has_liked,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
    }


def _to_comment_receipt(r) -> dict:
    return {
        "actionId": r.action_id,
        "success": r.success,
        "reason": r.reason,
    }


def _to_direct_participant(p) -> dict:
    return {
        "userId": p.user_id,
        "username": p.username,
        "fullName": p.full_name,
        "profilePicUrl": p.profile_pic_url,
        "isPrivate": p.is_private,
    }


def _to_direct_message(m) -> dict:
    return {
        "directMessageId": m.direct_message_id,
        "directThreadId": m.direct_thread_id,
        "senderUserId": m.sender_user_id,
        "sentAt": m.sent_at.isoformat() if m.sent_at else None,
        "itemType": m.item_type,
        "text": m.text,
        "isShhMode": m.is_shh_mode,
    }


def _to_direct_thread_summary(t) -> dict:
    return {
        "directThreadId": t.direct_thread_id,
        "pk": t.pk,
        "participants": [_to_direct_participant(p) for p in t.participants],
        "lastMessage": _to_direct_message(t.last_message) if t.last_message else None,
        "isPending": t.is_pending,
    }


def _to_direct_thread_detail(t) -> dict:
    return {
        "summary": _to_direct_thread_summary(t.summary),
        "messages": [_to_direct_message(m) for m in t.messages],
    }


def _to_direct_receipt(r) -> dict:
    return {
        "actionId": r.action_id,
        "success": r.success,
        "reason": r.reason,
    }


def _to_highlight_cover(c) -> dict | None:
    if c is None:
        return None
    return {
        "mediaId": c.media_id,
        "imageUrl": c.image_url,
        "cropRect": c.crop_rect,
    }


def _to_highlight_summary(h) -> dict:
    return {
        "pk": h.pk,
        "highlightId": h.highlight_id,
        "title": h.title,
        "createdAt": h.created_at.isoformat() if h.created_at else None,
        "isPinned": h.is_pinned,
        "mediaCount": h.media_count,
        "latestReelMedia": h.latest_reel_media,
        "ownerUsername": h.owner_username,
        "cover": _to_highlight_cover(h.cover),
    }


def _to_highlight_detail(h) -> dict:
    return {
        "summary": _to_highlight_summary(h.summary),
        "storyIds": h.story_ids,
        "items": [_to_story_summary(s) for s in h.items],
    }


def _to_highlight_receipt(r) -> dict:
    return {
        "actionId": r.action_id,
        "success": r.success,
        "reason": r.reason,
    }


def _to_insight(i) -> dict:
    return {
        "mediaPk": i.media_pk,
        "reachCount": i.reach_count,
        "impressionCount": i.impression_count,
        "likeCount": i.like_count,
        "commentCount": i.comment_count,
        "shareCount": i.share_count,
        "saveCount": i.save_count,
        "videoViewCount": i.video_view_count,
        "extraMetrics": i.extra_metrics,
    }
