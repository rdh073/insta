"""Instagram vertical router package.

Compatibility note:
- Keeps the historical import path `app.adapters.http.routers.instagram`.
- Re-exports the top-level `router` and legacy symbols previously defined
  in the monolithic `instagram.py` module.
"""

from __future__ import annotations

from fastapi import APIRouter

from .capabilities import get_instagram_capabilities, router as capabilities_router
from .collection import (
    get_collection_posts,
    list_collections,
    router as collection_router,
)
from .comment import (
    create_comment,
    delete_comment,
    like_comment,
    list_comments,
    list_comments_page,
    pin_comment,
    router as comment_router,
    unlike_comment,
    unpin_comment,
)
from .direct import (
    approve_pending_direct_thread,
    delete_direct_message,
    find_or_create_direct_thread,
    get_direct_thread,
    list_direct_messages,
    list_inbox,
    list_pending_inbox,
    mark_direct_thread_seen,
    router as direct_router,
    search_direct_threads,
    send_direct_message,
    send_direct_to_thread,
    send_direct_to_users,
)
from .hashtag import (
    get_hashtag,
    get_hashtag_recent_posts,
    get_hashtag_top_posts,
    router as hashtag_router,
    search_hashtags,
)
from .highlight import (
    add_highlight_stories,
    change_highlight_title,
    create_highlight,
    delete_highlight,
    get_highlight,
    get_highlight_pk_from_url,
    list_user_highlights,
    remove_highlight_stories,
    router as highlight_router,
)
from .identity import (
    get_authenticated_identity,
    get_public_user_by_username,
    router as identity_router,
)
from .insight import get_media_insight, list_media_insights, router as insight_router
from .mappers import (
    _to_comment,
    _to_comment_receipt,
    _to_direct_message,
    _to_direct_participant,
    _to_direct_receipt,
    _to_direct_search_user,
    _to_direct_thread_detail,
    _to_direct_thread_summary,
    _to_highlight_cover,
    _to_highlight_detail,
    _to_highlight_receipt,
    _to_highlight_summary,
    _to_insight,
    _to_media,
    _to_oembed,
    _to_public_profile,
    _to_resource,
    _to_story_detail,
    _to_story_receipt,
    _to_story_summary,
)
from .media import (
    get_media_by_code,
    get_media_by_pk,
    get_media_oembed,
    get_user_medias,
    router as media_router,
)
from .relationships import (
    BatchRelationshipRequest,
    batch_follow,
    batch_unfollow,
    close_friend_add,
    close_friend_remove,
    follow_user,
    list_followers,
    list_following,
    remove_follower,
    router as relationships_router,
    search_followers,
    search_following,
    unfollow_user,
)
from .story import (
    delete_story,
    get_story,
    get_story_pk_from_url,
    list_user_stories,
    mark_story_seen,
    publish_story,
    router as story_router,
)

router = APIRouter(prefix="/api/instagram", tags=["instagram"])

router.include_router(capabilities_router)
router.include_router(identity_router)
router.include_router(relationships_router)
router.include_router(media_router)
router.include_router(story_router)
router.include_router(hashtag_router)
router.include_router(highlight_router)
router.include_router(collection_router)
router.include_router(insight_router)
router.include_router(comment_router)
router.include_router(direct_router)

__all__ = [
    "router",
    "get_instagram_capabilities",
    "get_authenticated_identity",
    "get_public_user_by_username",
    "list_followers",
    "list_following",
    "search_followers",
    "search_following",
    "follow_user",
    "unfollow_user",
    "remove_follower",
    "close_friend_add",
    "close_friend_remove",
    "BatchRelationshipRequest",
    "batch_follow",
    "batch_unfollow",
    "get_media_by_pk",
    "get_media_by_code",
    "get_user_medias",
    "get_media_oembed",
    "get_story_pk_from_url",
    "get_story",
    "list_user_stories",
    "publish_story",
    "delete_story",
    "mark_story_seen",
    "search_hashtags",
    "get_hashtag",
    "get_hashtag_top_posts",
    "get_hashtag_recent_posts",
    "get_highlight_pk_from_url",
    "get_highlight",
    "list_user_highlights",
    "create_highlight",
    "change_highlight_title",
    "add_highlight_stories",
    "remove_highlight_stories",
    "delete_highlight",
    "list_collections",
    "get_collection_posts",
    "get_media_insight",
    "list_media_insights",
    "create_comment",
    "list_comments",
    "list_comments_page",
    "delete_comment",
    "like_comment",
    "unlike_comment",
    "pin_comment",
    "unpin_comment",
    "send_direct_message",
    "find_or_create_direct_thread",
    "send_direct_to_thread",
    "send_direct_to_users",
    "delete_direct_message",
    "approve_pending_direct_thread",
    "mark_direct_thread_seen",
    "list_inbox",
    "list_pending_inbox",
    "get_direct_thread",
    "list_direct_messages",
    "search_direct_threads",
    "_to_public_profile",
    "_to_media",
    "_to_resource",
    "_to_oembed",
    "_to_story_summary",
    "_to_story_detail",
    "_to_story_receipt",
    "_to_comment",
    "_to_comment_receipt",
    "_to_direct_participant",
    "_to_direct_search_user",
    "_to_direct_message",
    "_to_direct_thread_summary",
    "_to_direct_thread_detail",
    "_to_direct_receipt",
    "_to_highlight_cover",
    "_to_highlight_summary",
    "_to_highlight_detail",
    "_to_highlight_receipt",
    "_to_insight",
]
