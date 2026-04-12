"""Write-oriented engagement tools for AI registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .core import ToolRegistry, schema

if TYPE_CHECKING:
    from .builder import ToolBuilderContext


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


def _resolve_account(context: "ToolBuilderContext", username: str) -> Optional[str]:
    return context.resolve_account(username)


def register_highlight_write_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register highlight write tools."""

    def create_highlight_handler(args: dict) -> dict:
        if context.highlight_use_cases is None:
            return {"error": "Highlight use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = context.highlight_use_cases.create_highlight(
                account_id,
                title=args["title"],
                story_ids=[int(story_id) for story_id in args.get("story_ids", [])],
            )
            return {"success": True, "highlight": _highlight_summary_to_dict(result.summary)}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def delete_highlight_handler(args: dict) -> dict:
        if context.highlight_use_cases is None:
            return {"error": "Highlight use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = context.highlight_use_cases.delete_highlight(account_id, int(args["highlight_pk"]))
            return {"success": result.success, "reason": result.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "create_highlight",
        create_highlight_handler,
        schema(
            "create_highlight",
            "Create a new story highlight with a title and existing story IDs.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "title": {"type": "string", "description": "Highlight reel title"},
                "story_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of story PKs to include",
                },
            },
            required=["username", "title", "story_ids"],
        ),
    )

    registry.register(
        "delete_highlight",
        delete_highlight_handler,
        schema(
            "delete_highlight",
            "Delete a story highlight by its numeric pk.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "highlight_pk": {"type": "integer", "description": "Numeric highlight ID"},
            },
            required=["username", "highlight_pk"],
        ),
    )


def register_comment_write_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register comment write/moderation tools."""

    def create_comment_handler(args: dict) -> dict:
        if context.comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            comment = context.comment_use_cases.create_comment(
                account_id,
                args["media_id"],
                args["text"],
                reply_to_comment_id=args.get("reply_to_comment_id"),
            )
            return {"success": True, "comment": _comment_to_dict(comment)}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def delete_comment_handler(args: dict) -> dict:
        if context.comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = context.comment_use_cases.delete_comment(
                account_id,
                args["media_id"],
                int(args["comment_id"]),
            )
            return {"success": result.success, "reason": result.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def like_comment_handler(args: dict) -> dict:
        if context.comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = context.comment_use_cases.like_comment(account_id, int(args["comment_id"]))
            return {"success": result.success, "reason": result.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def unlike_comment_handler(args: dict) -> dict:
        if context.comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = context.comment_use_cases.unlike_comment(account_id, int(args["comment_id"]))
            return {"success": result.success, "reason": result.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def pin_comment_handler(args: dict) -> dict:
        if context.comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = context.comment_use_cases.pin_comment(
                account_id,
                args["media_id"],
                int(args["comment_id"]),
            )
            return {"success": result.success, "reason": result.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def unpin_comment_handler(args: dict) -> dict:
        if context.comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = context.comment_use_cases.unpin_comment(
                account_id,
                args["media_id"],
                int(args["comment_id"]),
            )
            return {"success": result.success, "reason": result.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "create_comment",
        create_comment_handler,
        schema(
            "create_comment",
            "Post a comment on an Instagram post. Can reply to an existing comment.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "media_id": {"type": "string", "description": "Instagram media ID to comment on"},
                "text": {"type": "string", "description": "Comment text"},
                "reply_to_comment_id": {"type": "integer", "description": "Optional comment PK to reply to"},
            },
            required=["username", "media_id", "text"],
        ),
    )

    registry.register(
        "delete_comment",
        delete_comment_handler,
        schema(
            "delete_comment",
            "Delete a comment by its ID from an Instagram post.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "media_id": {"type": "string", "description": "Instagram media ID"},
                "comment_id": {"type": "integer", "description": "Numeric comment ID to delete"},
            },
            required=["username", "media_id", "comment_id"],
        ),
    )

    registry.register(
        "like_comment",
        like_comment_handler,
        schema(
            "like_comment",
            "Like a comment by its ID.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "comment_id": {"type": "integer", "description": "Numeric comment ID to like"},
            },
            required=["username", "comment_id"],
        ),
    )

    registry.register(
        "unlike_comment",
        unlike_comment_handler,
        schema(
            "unlike_comment",
            "Unlike a comment by its ID.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "comment_id": {"type": "integer", "description": "Numeric comment ID to unlike"},
            },
            required=["username", "comment_id"],
        ),
    )

    registry.register(
        "pin_comment",
        pin_comment_handler,
        schema(
            "pin_comment",
            "Pin a comment on a post owned by the account. Only works on own posts.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "media_id": {
                    "type": "string",
                    "description": "Instagram media ID (must be owned by account)",
                },
                "comment_id": {"type": "integer", "description": "Numeric comment ID to pin"},
            },
            required=["username", "media_id", "comment_id"],
        ),
    )

    registry.register(
        "unpin_comment",
        unpin_comment_handler,
        schema(
            "unpin_comment",
            "Unpin a pinned comment on a post owned by the account.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "media_id": {
                    "type": "string",
                    "description": "Instagram media ID (must be owned by account)",
                },
                "comment_id": {"type": "integer", "description": "Numeric comment ID to unpin"},
            },
            required=["username", "media_id", "comment_id"],
        ),
    )


def register_send_direct_message_tool(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register direct-message send-by-username tool."""

    def send_direct_message_handler(args: dict) -> dict:
        if context.direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        recipient = args.get("recipient_username", "").lstrip("@")
        text = args.get("text", "")
        if not recipient:
            return {"error": "recipient_username is required"}
        if not text:
            return {"error": "text is required"}
        try:
            message = context.direct_use_cases.send_to_username(account_id, recipient, text)
            return {
                "success": True,
                "thread_id": message.direct_thread_id,
                "message_id": message.direct_message_id,
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "send_direct_message",
        send_direct_message_handler,
        schema(
            "send_direct_message",
            "Send a direct message to another Instagram user.",
            properties={
                "username": {"type": "string", "description": "Authenticated sender account username"},
                "recipient_username": {"type": "string", "description": "Recipient Instagram username"},
                "text": {"type": "string", "description": "Message text to send"},
            },
            required=["username", "recipient_username", "text"],
        ),
    )


def register_direct_thread_write_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register direct thread write tools."""

    def send_to_thread_handler(args: dict) -> dict:
        if context.direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        thread_id = args.get("thread_id", "")
        text = args.get("text", "")
        if not thread_id:
            return {"error": "thread_id is required"}
        if not text:
            return {"error": "text is required"}
        try:
            message = context.direct_use_cases.send_to_thread(account_id, thread_id, text)
            return {
                "success": True,
                "thread_id": message.direct_thread_id,
                "message_id": message.direct_message_id,
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def find_or_create_thread_handler(args: dict) -> dict:
        if context.direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        usernames = [u.lstrip("@") for u in args.get("participant_usernames", []) if u]
        if not usernames:
            return {"error": "participant_usernames is required and must not be empty"}
        try:
            thread = context.direct_use_cases.find_or_create_thread_with_usernames(account_id, usernames)
            return _thread_to_dict(thread)
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def delete_message_handler(args: dict) -> dict:
        if context.direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        thread_id = args.get("thread_id", "")
        message_id = args.get("message_id", "")
        if not thread_id:
            return {"error": "thread_id is required"}
        if not message_id:
            return {"error": "message_id is required"}
        try:
            receipt = context.direct_use_cases.delete_message(account_id, thread_id, message_id)
            return {"success": receipt.success, "reason": receipt.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "send_message_to_thread",
        send_to_thread_handler,
        schema(
            "send_message_to_thread",
            "Send a direct message to an existing thread by thread ID.",
            properties={
                "username": {"type": "string", "description": "Authenticated sender account username"},
                "thread_id": {"type": "string", "description": "Direct thread ID to send message to"},
                "text": {"type": "string", "description": "Message text to send"},
            },
            required=["username", "thread_id", "text"],
        ),
    )

    registry.register(
        "find_or_create_direct_thread",
        find_or_create_thread_handler,
        schema(
            "find_or_create_direct_thread",
            "Find an existing direct thread with participants or create a new one.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "participant_usernames": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of participant Instagram usernames",
                },
            },
            required=["username", "participant_usernames"],
        ),
    )

    registry.register(
        "delete_direct_message",
        delete_message_handler,
        schema(
            "delete_direct_message",
            "Delete a message from a direct thread.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "thread_id": {"type": "string", "description": "Direct thread ID"},
                "message_id": {"type": "string", "description": "Message ID to delete"},
            },
            required=["username", "thread_id", "message_id"],
        ),
    )


def register_relationship_primary_write_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register primary relationship write tools."""

    def follow_user_handler(args: dict) -> dict:
        if context.relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        target = args.get("target_username", "").lstrip("@")
        if not target:
            return {"error": "target_username is required"}
        try:
            success = context.relationship_use_cases.follow_user(account_id, target)
            return {"success": success, "action": "follow", "target": target}
        except ValueError as exc:
            return {"error": str(exc)}

    def unfollow_user_handler(args: dict) -> dict:
        if context.relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        target = args.get("target_username", "").lstrip("@")
        if not target:
            return {"error": "target_username is required"}
        try:
            success = context.relationship_use_cases.unfollow_user(account_id, target)
            return {"success": success, "action": "unfollow", "target": target}
        except ValueError as exc:
            return {"error": str(exc)}

    registry.register(
        "follow_user",
        follow_user_handler,
        schema(
            "follow_user",
            "Follow an Instagram user. Requires operator approval before execution.",
            properties={
                "username": {
                    "type": "string",
                    "description": "Authenticated account username performing the follow",
                },
                "target_username": {"type": "string", "description": "Instagram username to follow"},
            },
            required=["username", "target_username"],
        ),
    )

    registry.register(
        "unfollow_user",
        unfollow_user_handler,
        schema(
            "unfollow_user",
            "Unfollow an Instagram user. Requires operator approval before execution.",
            properties={
                "username": {
                    "type": "string",
                    "description": "Authenticated account username performing the unfollow",
                },
                "target_username": {"type": "string", "description": "Instagram username to unfollow"},
            },
            required=["username", "target_username"],
        ),
    )


def register_relationship_management_write_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register additional relationship management write tools."""

    def remove_follower_handler(args: dict) -> dict:
        if context.relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        target = args.get("target_username", "").lstrip("@")
        if not target:
            return {"error": "target_username is required"}
        try:
            success = context.relationship_use_cases.remove_follower(account_id, target)
            return {"success": success, "action": "remove_follower", "target": target}
        except ValueError as exc:
            return {"error": str(exc)}

    def close_friend_add_handler(args: dict) -> dict:
        if context.relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        target = args.get("target_username", "").lstrip("@")
        if not target:
            return {"error": "target_username is required"}
        try:
            success = context.relationship_use_cases.close_friend_add(account_id, target)
            return {"success": success, "action": "close_friend_add", "target": target}
        except ValueError as exc:
            return {"error": str(exc)}

    def close_friend_remove_handler(args: dict) -> dict:
        if context.relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        target = args.get("target_username", "").lstrip("@")
        if not target:
            return {"error": "target_username is required"}
        try:
            success = context.relationship_use_cases.close_friend_remove(account_id, target)
            return {"success": success, "action": "close_friend_remove", "target": target}
        except ValueError as exc:
            return {"error": str(exc)}

    registry.register(
        "remove_follower",
        remove_follower_handler,
        schema(
            "remove_follower",
            "Remove a follower from your account without blocking. Requires operator approval.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "target_username": {"type": "string", "description": "Follower username to remove"},
            },
            required=["username", "target_username"],
        ),
    )

    registry.register(
        "close_friend_add",
        close_friend_add_handler,
        schema(
            "close_friend_add",
            "Add a user to the Close Friends list for story audience targeting. Requires operator approval.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "target_username": {"type": "string", "description": "Username to add to Close Friends"},
            },
            required=["username", "target_username"],
        ),
    )

    registry.register(
        "close_friend_remove",
        close_friend_remove_handler,
        schema(
            "close_friend_remove",
            "Remove a user from the Close Friends list. Requires operator approval.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "target_username": {
                    "type": "string",
                    "description": "Username to remove from Close Friends",
                },
            },
            required=["username", "target_username"],
        ),
    )


def register_media_write_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register media engagement write tools."""

    def like_post_handler(args: dict) -> dict:
        if context.media_use_cases is None:
            return {"error": "Media use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        media_id = args.get("media_id", "")
        if not media_id:
            return {"error": "media_id is required"}
        try:
            success = context.media_use_cases.like_media(account_id, media_id)
            return {"success": success, "action": "like", "media_id": media_id}
        except ValueError as exc:
            return {"error": str(exc)}

    def unlike_post_handler(args: dict) -> dict:
        if context.media_use_cases is None:
            return {"error": "Media use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(context, username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        media_id = args.get("media_id", "")
        if not media_id:
            return {"error": "media_id is required"}
        try:
            success = context.media_use_cases.unlike_media(account_id, media_id)
            return {"success": success, "action": "unlike", "media_id": media_id}
        except ValueError as exc:
            return {"error": str(exc)}

    registry.register(
        "like_post",
        like_post_handler,
        schema(
            "like_post",
            "Like an Instagram post. Requires operator approval before execution.",
            properties={
                "username": {
                    "type": "string",
                    "description": "Authenticated account username performing the like",
                },
                "media_id": {
                    "type": "string",
                    "description": "Instagram media ID string (e.g. '3488123456_25025320')",
                },
            },
            required=["username", "media_id"],
        ),
    )

    registry.register(
        "unlike_post",
        unlike_post_handler,
        schema(
            "unlike_post",
            "Remove a like from an Instagram post. Requires operator approval before execution.",
            properties={
                "username": {
                    "type": "string",
                    "description": "Authenticated account username removing the like",
                },
                "media_id": {"type": "string", "description": "Instagram media ID string"},
            },
            required=["username", "media_id"],
        ),
    )
