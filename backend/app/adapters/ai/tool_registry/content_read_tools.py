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


def _story_detail_to_dict(story) -> dict:
    return {
        "summary": _story_summary_to_dict(story.summary),
        "link_count": story.link_count,
        "mention_count": story.mention_count,
        "hashtag_count": story.hashtag_count,
        "location_count": story.location_count,
        "sticker_count": story.sticker_count,
    }


def _highlight_summary_to_dict(highlight) -> dict:
    return {
        "pk": highlight.pk,
        "highlight_id": highlight.highlight_id,
        "title": highlight.title,
        "media_count": highlight.media_count,
        "owner_username": highlight.owner_username,
    }


def _highlight_detail_to_dict(highlight) -> dict:
    return {
        "summary": _highlight_summary_to_dict(highlight.summary),
        "story_ids": list(highlight.story_ids or []),
        "items": [_story_summary_to_dict(story) for story in (highlight.items or [])],
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


def _direct_search_user_to_dict(user) -> dict:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "full_name": user.full_name,
        "profile_pic_url": user.profile_pic_url,
        "is_private": user.is_private,
        "is_verified": user.is_verified,
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


def _account_insight_to_dict(insight) -> dict:
    return {
        "followers_count": insight.followers_count,
        "following_count": insight.following_count,
        "media_count": insight.media_count,
        "impressions_last_7_days": insight.impressions_last_7_days,
        "reach_last_7_days": insight.reach_last_7_days,
        "profile_views_last_7_days": insight.profile_views_last_7_days,
        "website_clicks_last_7_days": insight.website_clicks_last_7_days,
        "follower_change_last_7_days": insight.follower_change_last_7_days,
        "extra_metrics": insight.extra_metrics,
    }


def _media_oembed_to_dict(oembed) -> dict:
    return {
        "media_id": oembed.media_id,
        "author_name": oembed.author_name,
        "author_url": oembed.author_url,
        "author_id": oembed.author_id,
        "title": oembed.title,
        "provider_name": oembed.provider_name,
        "html": oembed.html,
        "thumbnail_url": oembed.thumbnail_url,
        "width": oembed.width,
        "height": oembed.height,
        "can_view": oembed.can_view,
    }


def _hashtag_to_dict(hashtag) -> dict:
    return {
        "id": hashtag.id,
        "name": hashtag.name,
        "media_count": hashtag.media_count,
        "profile_pic_url": hashtag.profile_pic_url,
    }


def _collection_to_dict(collection) -> dict:
    return {
        "pk": collection.pk,
        "name": collection.name,
        "media_count": collection.media_count,
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

    def get_media_oembed_handler(args: dict) -> dict:
        if context.media_use_cases is None:
            return {"error": "Media use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            oembed = context.media_use_cases.get_media_oembed(account_id, str(args["url"]))
            return _media_oembed_to_dict(oembed)
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

    registry.register(
        "get_media_oembed",
        get_media_oembed_handler,
        schema(
            "get_media_oembed",
            "Fetch oEmbed metadata for a public Instagram media URL.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "url": {"type": "string", "description": "Public Instagram media URL"},
            },
            required=["username", "url"],
        ),
    )


def register_story_read_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register story read tools."""

    def get_story_handler(args: dict) -> dict:
        if context.story_use_cases is None:
            return {"error": "Story use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            use_cache = args.get("use_cache", True)
            if isinstance(use_cache, str):
                use_cache = use_cache.strip().lower() not in {"0", "false", "no"}
            story = context.story_use_cases.get_story(
                account_id,
                int(args["story_pk"]),
                use_cache=bool(use_cache),
            )
            return _story_detail_to_dict(story)
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

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
        "get_story",
        get_story_handler,
        schema(
            "get_story",
            "Get one story by numeric story_pk with overlay counters.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "story_pk": {"type": "integer", "description": "Numeric story primary key"},
                "use_cache": {
                    "type": "boolean",
                    "description": "Use cached story metadata when available (default true)",
                    "default": True,
                },
            },
            required=["username", "story_pk"],
        ),
    )

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

    def get_highlight_handler(args: dict) -> dict:
        if context.highlight_use_cases is None:
            return {"error": "Highlight use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            highlight = context.highlight_use_cases.get_highlight(account_id, int(args["highlight_pk"]))
            return _highlight_detail_to_dict(highlight)
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

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
        "get_highlight",
        get_highlight_handler,
        schema(
            "get_highlight",
            "Get one highlight by numeric highlight_pk including story items.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "highlight_pk": {"type": "integer", "description": "Numeric highlight primary key"},
            },
            required=["username", "highlight_pk"],
        ),
    )

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


def register_discovery_read_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register hashtag and collection discovery/read tools."""

    def search_hashtags_handler(args: dict) -> dict:
        if context.hashtag_use_cases is None:
            return {"error": "Hashtag use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            hashtags = context.hashtag_use_cases.search_hashtags(account_id, str(args["query"]))
            return {
                "count": len(hashtags),
                "hashtags": [_hashtag_to_dict(hashtag) for hashtag in hashtags],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def get_hashtag_handler(args: dict) -> dict:
        if context.hashtag_use_cases is None:
            return {"error": "Hashtag use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            hashtag = context.hashtag_use_cases.get_hashtag(account_id, str(args["name"]))
            return _hashtag_to_dict(hashtag)
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def list_collections_handler(args: dict) -> dict:
        if context.collection_use_cases is None:
            return {"error": "Collection use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            collections = context.collection_use_cases.list_collections(account_id)
            return {
                "count": len(collections),
                "collections": [_collection_to_dict(collection) for collection in collections],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def list_liked_medias_handler(args: dict) -> dict:
        if context.collection_use_cases is None:
            return {"error": "Collection use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            medias = context.collection_use_cases.list_liked_medias(
                account_id,
                amount=int(args.get("amount", 21)),
                last_media_pk=int(args.get("last_media_pk", 0)),
            )
            return {
                "count": len(medias),
                "posts": [_media_to_dict(media) for media in medias],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "search_hashtags",
        search_hashtags_handler,
        schema(
            "search_hashtags",
            "Search hashtags by query string and return hashtag metadata candidates.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "query": {"type": "string", "description": "Hashtag query with or without #"},
            },
            required=["username", "query"],
        ),
    )

    registry.register(
        "get_hashtag",
        get_hashtag_handler,
        schema(
            "get_hashtag",
            "Fetch metadata for one hashtag by exact name.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "name": {"type": "string", "description": "Hashtag name with or without #"},
            },
            required=["username", "name"],
        ),
    )

    registry.register(
        "list_collections",
        list_collections_handler,
        schema(
            "list_collections",
            "List saved collections for the authenticated account.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
            },
            required=["username"],
        ),
    )

    registry.register(
        "list_liked_medias",
        list_liked_medias_handler,
        schema(
            "list_liked_medias",
            "List posts the authenticated account has liked. Supports pagination via last_media_pk cursor.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "amount": {"type": "integer", "description": "Number of posts to retrieve (default 21, max 200)"},
                "last_media_pk": {"type": "integer", "description": "Pagination cursor; 0 starts from beginning"},
            },
            required=["username"],
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
            users = context.direct_use_cases.search_threads(account_id, args["query"])
            return {
                "count": len(users),
                "users": [_direct_search_user_to_dict(user) for user in users],
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
            "Search direct users by username or keyword in direct inbox.",
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

    def get_account_insight_handler(args: dict) -> dict:
        if context.insight_use_cases is None:
            return {"error": "Insight use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            insight = context.insight_use_cases.get_account_insight(account_id)
            return _account_insight_to_dict(insight)
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
        "get_account_insight",
        get_account_insight_handler,
        schema(
            "get_account_insight",
            "Get account-level dashboard analytics: followers, reach/impressions last 7 days, profile views, website clicks, follower change.",
            properties={
                "username": {
                    "type": "string",
                    "description": "Authenticated account username",
                },
            },
            required=["username"],
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
                    "description": (
                        "Filter by post type: ALL, CAROUSEL_V2, IMAGE, SHOPPING, VIDEO "
                        "(legacy aliases accepted: PHOTO, CAROUSEL)"
                    ),
                    "enum": ["ALL", "CAROUSEL_V2", "IMAGE", "SHOPPING", "VIDEO"],
                    "default": "ALL",
                },
                "time_frame": {
                    "type": "string",
                    "description": (
                        "Time range: ONE_WEEK, ONE_MONTH, THREE_MONTHS, SIX_MONTHS, "
                        "ONE_YEAR, TWO_YEARS (legacy aliases accepted: WEEK, MONTH)"
                    ),
                    "enum": [
                        "ONE_WEEK",
                        "ONE_MONTH",
                        "THREE_MONTHS",
                        "SIX_MONTHS",
                        "ONE_YEAR",
                        "TWO_YEARS",
                    ],
                    "default": "TWO_YEARS",
                },
                "ordering": {
                    "type": "string",
                    "description": (
                        "Sort by: REACH_COUNT, LIKE_COUNT, FOLLOW, SHARE_COUNT, "
                        "BIO_LINK_CLICK, COMMENT_COUNT, IMPRESSION_COUNT, "
                        "PROFILE_VIEW, VIDEO_VIEW_COUNT, SAVE_COUNT "
                        "(legacy aliases accepted: IMPRESSIONS, ENGAGEMENT)"
                    ),
                    "enum": [
                        "BIO_LINK_CLICK",
                        "COMMENT_COUNT",
                        "FOLLOW",
                        "IMPRESSION_COUNT",
                        "LIKE_COUNT",
                        "PROFILE_VIEW",
                        "REACH_COUNT",
                        "SHARE_COUNT",
                        "SAVE_COUNT",
                        "VIDEO_VIEW_COUNT",
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
