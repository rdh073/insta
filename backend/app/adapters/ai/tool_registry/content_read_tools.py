"""Read-oriented content tools for AI registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .core import ToolRegistry, schema

if TYPE_CHECKING:
    from .builder import ToolBuilderContext


def _media_to_dict(media) -> dict:
    return {
        "post_id": media.pk,
        "code": media.code,
        "owner": media.owner_username,
        "caption_text": media.caption_text,
        "like_count": media.like_count,
        "comment_count": media.comment_count,
        "media_type": media.media_type,
        "product_type": media.product_type,
        "taken_at": media.taken_at.isoformat() if media.taken_at else None,
    }


def _story_summary_to_dict(story) -> dict:
    return {
        "pk": story.pk,
        "story_id": story.story_id,
        "media_type": story.media_type,
        "taken_at": story.taken_at.isoformat() if story.taken_at else None,
        "thumbnail_url": story.thumbnail_url,
        "owner_username": story.owner_username,
    }


def _highlight_summary_to_dict(highlight) -> dict:
    return {
        "pk": highlight.pk,
        "highlight_id": highlight.highlight_id,
        "title": highlight.title,
        "media_count": highlight.media_count,
        "owner_username": highlight.owner_username,
    }


def _comment_to_dict(comment) -> dict:
    return {
        "pk": comment.pk,
        "text": comment.text,
        "author": comment.author.username if comment.author else None,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "like_count": comment.like_count,
    }


def _thread_to_dict(thread) -> dict:
    return {
        "thread_id": thread.direct_thread_id,
        "participants": [participant.username for participant in (thread.participants or [])],
        "is_pending": thread.is_pending,
        "last_message": thread.last_message.text if thread.last_message else None,
    }


def _message_to_dict(message) -> dict:
    return {
        "message_id": message.direct_message_id,
        "thread_id": message.direct_thread_id,
        "sender_user_id": message.sender_user_id,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
        "item_type": message.item_type,
        "text": message.text,
    }


def _insight_to_dict(insight) -> dict:
    return {
        "media_pk": insight.media_pk,
        "reach_count": insight.reach_count,
        "impression_count": insight.impression_count,
        "like_count": insight.like_count,
        "comment_count": insight.comment_count,
        "share_count": insight.share_count,
        "save_count": insight.save_count,
        "video_view_count": insight.video_view_count,
    }


def _profile_to_dict(profile) -> dict:
    return {
        "user_id": profile.pk,
        "username": profile.username,
        "full_name": profile.full_name,
        "follower_count": profile.follower_count,
        "following_count": profile.following_count,
        "is_private": profile.is_private,
        "is_verified": profile.is_verified,
    }


def _resolve_account(context: "ToolBuilderContext", username: str) -> Optional[str]:
    """Return account_id or None. Explicit empty-string guard prevents
    ambiguous '@' lookup — callers that need a descriptive error should
    check for empty username before calling."""
    return context.resolve_account(username)


def register_media_read_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register media read tools."""

    def get_media_by_pk_handler(args: dict) -> dict:
        if context.media_use_cases is None:
            return {"error": "Media use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            media = context.media_use_cases.get_media_by_pk(account_id, int(args["media_pk"]))
            return _media_to_dict(media)
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def get_media_by_code_handler(args: dict) -> dict:
        if context.media_use_cases is None:
            return {"error": "Media use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            media = context.media_use_cases.get_media_by_code(account_id, args["code"])
            return _media_to_dict(media)
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def get_user_medias_handler(args: dict) -> dict:
        if context.media_use_cases is None:
            return {"error": "Media use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            medias = context.media_use_cases.get_user_medias(
                account_id,
                int(args["user_id"]),
                amount=int(args.get("amount", 12)),
            )
            return {"count": len(medias), "posts": [_media_to_dict(media) for media in medias]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "get_media_by_pk",
        get_media_by_pk_handler,
        schema(
            "get_media_by_pk",
            "Fetch a single Instagram post by its numeric primary key (post_id).",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "media_pk": {"type": "integer", "description": "Numeric post ID"},
            },
            required=["username", "media_pk"],
        ),
    )

    registry.register(
        "get_media_by_code",
        get_media_by_code_handler,
        schema(
            "get_media_by_code",
            "Fetch a single Instagram post by its shortcode (the part after instagram.com/p/).",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "code": {"type": "string", "description": "Instagram post shortcode"},
            },
            required=["username", "code"],
        ),
    )

    registry.register(
        "get_user_medias",
        get_user_medias_handler,
        schema(
            "get_user_medias",
            "List recent posts for an Instagram user by their numeric user ID.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "user_id": {"type": "integer", "description": "Numeric Instagram user ID"},
                "amount": {
                    "type": "integer",
                    "description": "Number of posts to fetch (default 12)",
                    "default": 12,
                },
            },
            required=["username", "user_id"],
        ),
    )


def register_story_read_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register story read tools."""

    def list_user_stories_handler(args: dict) -> dict:
        if context.story_use_cases is None:
            return {"error": "Story use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            stories = context.story_use_cases.list_user_stories(
                account_id,
                int(args["user_id"]),
                amount=args.get("amount"),
            )
            return {
                "count": len(stories),
                "stories": [_story_summary_to_dict(story) for story in stories],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "list_user_stories",
        list_user_stories_handler,
        schema(
            "list_user_stories",
            "List active stories for an Instagram user by their numeric user ID.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "user_id": {"type": "integer", "description": "Numeric Instagram user ID"},
                "amount": {"type": "integer", "description": "Max stories to fetch (default all)"},
            },
            required=["username", "user_id"],
        ),
    )


def register_highlight_read_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register highlight read tools."""

    def list_user_highlights_handler(args: dict) -> dict:
        if context.highlight_use_cases is None:
            return {"error": "Highlight use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            highlights = context.highlight_use_cases.list_user_highlights(
                account_id,
                int(args["user_id"]),
            )
            return {
                "count": len(highlights),
                "highlights": [_highlight_summary_to_dict(highlight) for highlight in highlights],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "list_user_highlights",
        list_user_highlights_handler,
        schema(
            "list_user_highlights",
            "List all Instagram story highlights for a user by their numeric user ID.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "user_id": {"type": "integer", "description": "Numeric Instagram user ID"},
            },
            required=["username", "user_id"],
        ),
    )


def register_comment_read_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register comment read tools."""

    def list_comments_handler(args: dict) -> dict:
        if context.comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            comments = context.comment_use_cases.list_comments(
                account_id,
                args["media_id"],
                amount=int(args.get("amount", 0)),
            )
            return {
                "count": len(comments),
                "comments": [_comment_to_dict(comment) for comment in comments],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "list_comments",
        list_comments_handler,
        schema(
            "list_comments",
            "Fetch comments on an Instagram post by its media ID.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "media_id": {"type": "string", "description": "Instagram media ID"},
                "amount": {
                    "type": "integer",
                    "description": "Max comments to fetch (default all)",
                    "default": 0,
                },
            },
            required=["username", "media_id"],
        ),
    )


def register_direct_inbox_read_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register direct-message inbox/search read tools."""

    def list_inbox_threads_handler(args: dict) -> dict:
        if context.direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            threads = context.direct_use_cases.list_inbox_threads(
                account_id,
                amount=int(args.get("amount", 20)),
            )
            return {
                "count": len(threads),
                "threads": [_thread_to_dict(thread) for thread in threads],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def list_pending_threads_handler(args: dict) -> dict:
        if context.direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            threads = context.direct_use_cases.list_pending_threads(
                account_id,
                amount=int(args.get("amount", 20)),
            )
            return {
                "count": len(threads),
                "threads": [_thread_to_dict(thread) for thread in threads],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def search_threads_handler(args: dict) -> dict:
        if context.direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            threads = context.direct_use_cases.search_threads(account_id, args["query"])
            return {
                "count": len(threads),
                "threads": [_thread_to_dict(thread) for thread in threads],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "list_inbox_threads",
        list_inbox_threads_handler,
        schema(
            "list_inbox_threads",
            "List direct message inbox threads for an account.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "amount": {
                    "type": "integer",
                    "description": "Number of threads to return (default 20)",
                    "default": 20,
                },
            },
            required=["username"],
        ),
    )

    registry.register(
        "list_pending_threads",
        list_pending_threads_handler,
        schema(
            "list_pending_threads",
            "List pending (unaccepted) direct message requests for an account.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "amount": {
                    "type": "integer",
                    "description": "Number of threads to return (default 20)",
                    "default": 20,
                },
            },
            required=["username"],
        ),
    )

    registry.register(
        "search_threads",
        search_threads_handler,
        schema(
            "search_threads",
            "Search direct message threads by participant username or keyword.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "query": {"type": "string", "description": "Search query (username or keyword)"},
            },
            required=["username", "query"],
        ),
    )


def register_direct_thread_read_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register direct thread/message read tools."""

    def get_thread_handler(args: dict) -> dict:
        if context.direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            detail = context.direct_use_cases.get_thread(
                account_id,
                args["thread_id"],
                amount=int(args.get("amount", 20)),
            )
            return {
                **_thread_to_dict(detail.summary),
                "messages": [_message_to_dict(message) for message in detail.messages],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def list_messages_handler(args: dict) -> dict:
        if context.direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            messages = context.direct_use_cases.list_messages(
                account_id,
                args["thread_id"],
                amount=int(args.get("amount", 20)),
            )
            return {
                "count": len(messages),
                "messages": [_message_to_dict(message) for message in messages],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "get_direct_thread",
        get_thread_handler,
        schema(
            "get_direct_thread",
            "Get a specific direct message thread with its messages.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "thread_id": {"type": "string", "description": "Direct thread ID"},
                "amount": {
                    "type": "integer",
                    "description": "Number of messages to retrieve (default 20)",
                    "default": 20,
                },
            },
            required=["username", "thread_id"],
        ),
    )

    registry.register(
        "list_direct_messages",
        list_messages_handler,
        schema(
            "list_direct_messages",
            "List messages in a direct message thread.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "thread_id": {"type": "string", "description": "Direct thread ID"},
                "amount": {
                    "type": "integer",
                    "description": "Number of messages to retrieve (default 20)",
                    "default": 20,
                },
            },
            required=["username", "thread_id"],
        ),
    )


def register_insight_read_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register media insight read tools."""

    def get_media_insight_handler(args: dict) -> dict:
        if context.insight_use_cases is None:
            return {"error": "Insight use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            insight = context.insight_use_cases.get_media_insight(account_id, int(args["media_pk"]))
            return _insight_to_dict(insight)
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def list_media_insights_handler(args: dict) -> dict:
        if context.insight_use_cases is None:
            return {"error": "Insight use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            results = context.insight_use_cases.list_media_insights(
                account_id,
                post_type=args.get("post_type", "ALL"),
                time_frame=args.get("time_frame", "TWO_YEARS"),
                ordering=args.get("ordering", "REACH_COUNT"),
                count=int(args.get("count", 0)),
            )
            return {
                "count": len(results),
                "insights": [_insight_to_dict(insight) for insight in results],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "get_media_insight",
        get_media_insight_handler,
        schema(
            "get_media_insight",
            "Get detailed analytics for a single post: reach, impressions, likes, comments, shares, saves.",
            properties={
                "username": {
                    "type": "string",
                    "description": "Authenticated account username (must own the post)",
                },
                "media_pk": {"type": "integer", "description": "Numeric post ID"},
            },
            required=["username", "media_pk"],
        ),
    )

    registry.register(
        "list_media_insights",
        list_media_insights_handler,
        schema(
            "list_media_insights",
            "List analytics for multiple posts with filtering by type, time frame, and sort order.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "post_type": {
                    "type": "string",
                    "description": "Filter by post type: ALL, PHOTO, VIDEO, CAROUSEL",
                    "enum": ["ALL", "PHOTO", "VIDEO", "CAROUSEL"],
                    "default": "ALL",
                },
                "time_frame": {
                    "type": "string",
                    "description": "Time range: TWO_YEARS, ONE_YEAR, SIX_MONTHS, MONTH, WEEK",
                    "enum": ["TWO_YEARS", "ONE_YEAR", "SIX_MONTHS", "MONTH", "WEEK"],
                    "default": "TWO_YEARS",
                },
                "ordering": {
                    "type": "string",
                    "description": "Sort by: REACH_COUNT, IMPRESSIONS, ENGAGEMENT, LIKE_COUNT, COMMENT_COUNT, SHARE_COUNT, SAVE_COUNT",
                    "enum": [
                        "REACH_COUNT",
                        "IMPRESSIONS",
                        "ENGAGEMENT",
                        "LIKE_COUNT",
                        "COMMENT_COUNT",
                        "SHARE_COUNT",
                        "SAVE_COUNT",
                    ],
                    "default": "REACH_COUNT",
                },
                "count": {"type": "integer", "description": "Max posts to return (default all)", "default": 0},
            },
            required=["username"],
        ),
    )


def register_relationship_read_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register relationship read/search tools."""

    def list_followers_handler(args: dict) -> dict:
        if context.relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        target = args.get("target_username", username).lstrip("@")
        try:
            followers = context.relationship_use_cases.list_followers(
                account_id,
                target,
                amount=int(args.get("amount", 50)),
            )
            return {
                "count": len(followers),
                "followers": [_profile_to_dict(profile) for profile in followers],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def list_following_handler(args: dict) -> dict:
        if context.relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        target = args.get("target_username", username).lstrip("@")
        try:
            following = context.relationship_use_cases.list_following(
                account_id,
                target,
                amount=int(args.get("amount", 50)),
            )
            return {
                "count": len(following),
                "following": [_profile_to_dict(profile) for profile in following],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def search_followers_handler(args: dict) -> dict:
        if context.relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        target = args.get("target_username", username).lstrip("@")
        query = args.get("query", "")
        if not query:
            return {"error": "query is required"}
        try:
            results = context.relationship_use_cases.search_followers(account_id, target, query=query)
            return {
                "count": len(results),
                "followers": [_profile_to_dict(profile) for profile in results],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def search_following_handler(args: dict) -> dict:
        if context.relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        target = args.get("target_username", username).lstrip("@")
        query = args.get("query", "")
        if not query:
            return {"error": "query is required"}
        try:
            results = context.relationship_use_cases.search_following(account_id, target, query=query)
            return {
                "count": len(results),
                "following": [_profile_to_dict(profile) for profile in results],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "list_followers",
        list_followers_handler,
        schema(
            "list_followers",
            "List followers of an Instagram account.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "target_username": {
                    "type": "string",
                    "description": "Username whose followers to list (defaults to authenticated account)",
                },
                "amount": {
                    "type": "integer",
                    "description": "Number of followers to return (default 50)",
                    "default": 50,
                },
            },
            required=["username"],
        ),
    )

    registry.register(
        "list_following",
        list_following_handler,
        schema(
            "list_following",
            "List accounts followed by an Instagram account.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "target_username": {
                    "type": "string",
                    "description": "Username whose following list to retrieve (defaults to authenticated account)",
                },
                "amount": {
                    "type": "integer",
                    "description": "Number of following accounts to return (default 50)",
                    "default": 50,
                },
            },
            required=["username"],
        ),
    )

    registry.register(
        "search_followers",
        search_followers_handler,
        schema(
            "search_followers",
            "Search within an Instagram user's follower list by keyword.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "target_username": {
                    "type": "string",
                    "description": "Username whose followers to search (defaults to authenticated account)",
                },
                "query": {"type": "string", "description": "Search query string"},
            },
            required=["username", "query"],
        ),
    )

    registry.register(
        "search_following",
        search_following_handler,
        schema(
            "search_following",
            "Search within an Instagram user's following list by keyword.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "target_username": {
                    "type": "string",
                    "description": "Username whose following to search (defaults to authenticated account)",
                },
                "query": {"type": "string", "description": "Search query string"},
            },
            required=["username", "query"],
        ),
    )
