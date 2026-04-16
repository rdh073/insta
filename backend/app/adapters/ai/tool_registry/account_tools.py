"""Account-scoped tools for AI registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .core import ToolRegistry, schema

if TYPE_CHECKING:
    from .builder import ToolBuilderContext


def register_account_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register account/profile/auth/proxy tools."""

    def list_accounts_handler(_args: dict) -> dict:
        return context.profile_usecases.get_accounts_summary()

    def get_account_info_handler(args: dict) -> dict:
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}

        result = context.profile_usecases.get_account_info(account_id)
        if result.error:
            return {"error": result.error}

        return {
            "username": result.username,
            "fullName": result.full_name,
            "biography": result.biography,
            "followers": result.followers,
            "following": result.following,
            "mediaCount": result.media_count,
            "isPrivate": result.is_private,
            "isVerified": result.is_verified,
            "isBusiness": result.is_business,
        }

    def relogin_account_handler(args: dict) -> dict:
        username = args.get("username", "")
        return context.auth_usecases.relogin_account_by_username(username)

    def logout_account_handler(args: dict) -> dict:
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        username = args.get("username", "").lstrip("@")
        try:
            context.auth_usecases.logout_account(account_id, detail="ai_tool")
        except ValueError as exc:
            return {"error": str(exc)}
        return {"success": True, "message": f"@{username} logged out and removed"}

    def set_account_proxy_handler(args: dict) -> dict:
        username = args.get("username", "").lstrip("@")
        proxy_url = args.get("proxy_url", "")
        account_id = context.profile_usecases.find_by_username(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            context.proxy_usecases.set_account_proxy(account_id, proxy_url)
        except ValueError as exc:
            return {"error": str(exc)}
        return {
            "success": True,
            "username": username,
            "proxy": proxy_url,
            "message": f"Proxy updated for @{username}",
        }

    async def check_proxy_handler(args: dict) -> dict:
        proxy_url = args.get("proxy_url", "")
        if not proxy_url:
            return {"error": "proxy_url is required"}
        result = await context.proxy_usecases.check_proxy(proxy_url)
        return {
            "proxy_url": result.proxy_url,
            "reachable": result.reachable,
            "latency_ms": result.latency_ms,
            "ip_address": result.ip_address,
            "error": result.error,
            "status": "ok" if result.reachable else "failed",
        }

    registry.register(
        "list_accounts",
        list_accounts_handler,
        schema(
            "list_accounts",
            "List all Instagram accounts managed in this system with their current status, followers, following counts, and proxy settings.",
        ),
    )

    registry.register(
        "get_account_info",
        get_account_info_handler,
        schema(
            "get_account_info",
            "Fetch fresh account statistics from Instagram for a specific account (followers, following, bio, media count).",
            properties={
                "username": {
                    "type": "string",
                    "description": "Instagram username (with or without @)",
                },
            },
            required=["username"],
        ),
    )

    registry.register(
        "relogin_account",
        relogin_account_handler,
        schema(
            "relogin_account",
            "Re-authenticate an Instagram account. Use when an account shows error status, challenge, or connection issues.",
            properties={
                "username": {"type": "string", "description": "Instagram username to re-login"},
            },
            required=["username"],
        ),
    )

    registry.register(
        "logout_account",
        logout_account_handler,
        schema(
            "logout_account",
            "Logout and remove an Instagram account from the system.",
            properties={
                "username": {"type": "string", "description": "Instagram username to logout"},
            },
            required=["username"],
        ),
    )

    registry.register(
        "set_account_proxy",
        set_account_proxy_handler,
        schema(
            "set_account_proxy",
            "Configure or update the proxy server for a specific Instagram account.",
            properties={
                "username": {"type": "string", "description": "Instagram username"},
                "proxy_url": {
                    "type": "string",
                    "description": "Proxy URL e.g. http://user:pass@host:port or socks5://host:port",
                },
            },
            required=["username", "proxy_url"],
        ),
    )

    registry.register(
        "check_proxy",
        check_proxy_handler,
        schema(
            "check_proxy",
            "Test if a proxy URL is reachable and measure its round-trip latency. Returns the exit IP address as seen by the test target (useful to confirm the proxy routes traffic correctly).",
            properties={
                "proxy_url": {
                    "type": "string",
                    "description": "Proxy URL to test, e.g. http://user:pass@host:port or socks5://host:port",
                },
            },
            required=["proxy_url"],
        ),
    )

    def _serialize_account_profile(profile) -> dict:
        return {
            "id": profile.id,
            "username": profile.username,
            "isPrivate": profile.is_private,
            "fullName": profile.full_name,
            "biography": profile.biography,
            "externalUrl": profile.external_url,
            "avatar": profile.profile_pic_url,
            "presenceDisabled": profile.presence_disabled,
        }

    def set_account_privacy_handler(args: dict) -> dict:
        if context.edit_usecases is None:
            return {"error": "Account edit use cases are not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        private = bool(args.get("private", False))
        try:
            profile = (
                context.edit_usecases.set_private(account_id)
                if private
                else context.edit_usecases.set_public(account_id)
            )
        except ValueError as exc:
            return {"error": str(exc)}
        return {"success": True, **_serialize_account_profile(profile)}

    def edit_account_profile_handler(args: dict) -> dict:
        if context.edit_usecases is None:
            return {"error": "Account edit use cases are not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        kwargs = {
            key: args[key]
            for key in ("first_name", "biography", "external_url")
            if key in args and args[key] is not None
        }
        if not kwargs:
            return {
                "error": "Provide at least one of: first_name, biography, external_url"
            }
        try:
            profile = context.edit_usecases.edit_profile(account_id, **kwargs)
        except ValueError as exc:
            return {"error": str(exc)}
        return {"success": True, **_serialize_account_profile(profile)}

    def set_account_presence_handler(args: dict) -> dict:
        if context.edit_usecases is None:
            return {"error": "Account edit use cases are not available"}
        account_id, error = context.resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        disabled = bool(args.get("disabled", False))
        try:
            profile = context.edit_usecases.set_presence_disabled(
                account_id, disabled
            )
        except ValueError as exc:
            return {"error": str(exc)}
        return {"success": True, **_serialize_account_profile(profile)}

    registry.register(
        "set_account_privacy",
        set_account_privacy_handler,
        schema(
            "set_account_privacy",
            "Switch the authenticated Instagram account between private and public visibility.",
            properties={
                "username": {
                    "type": "string",
                    "description": "Instagram username (with or without @)",
                },
                "private": {
                    "type": "boolean",
                    "description": "True = make account private; False = make it public",
                },
            },
            required=["username", "private"],
        ),
    )

    registry.register(
        "edit_account_profile",
        edit_account_profile_handler,
        schema(
            "edit_account_profile",
            "Edit the authenticated account's profile fields. Only provided fields are sent.",
            properties={
                "username": {
                    "type": "string",
                    "description": "Instagram username (with or without @)",
                },
                "first_name": {
                    "type": "string",
                    "description": "Display name (max length enforced by Instagram).",
                },
                "biography": {
                    "type": "string",
                    "description": "Profile bio text. Max 150 characters.",
                },
                "external_url": {
                    "type": "string",
                    "description": "Absolute http(s) link in bio. Empty string clears the link.",
                },
            },
            required=["username"],
        ),
    )

    registry.register(
        "set_account_presence",
        set_account_presence_handler,
        schema(
            "set_account_presence",
            "Toggle the 'show activity status' (last-active) presence flag for the account.",
            properties={
                "username": {
                    "type": "string",
                    "description": "Instagram username (with or without @)",
                },
                "disabled": {
                    "type": "boolean",
                    "description": "True hides last-active timestamps from other users; False shows them.",
                },
            },
            required=["username", "disabled"],
        ),
    )

    def list_pending_challenges_handler(_args: dict) -> dict:
        if context.challenge_usecases is None:
            return {"pending": [], "count": 0}
        pending = context.challenge_usecases.list_pending()
        return {
            "count": len(pending),
            "pending": [
                {
                    "account_id": p.account_id,
                    "username": p.username,
                    "method": p.method,
                    "contact_hint": p.contact_hint,
                    "created_at": p.created_at,
                }
                for p in pending
            ],
        }

    registry.register(
        "list_pending_challenges",
        list_pending_challenges_handler,
        schema(
            "list_pending_challenges",
            (
                "List Instagram accounts that are blocked on a login challenge "
                "waiting for the operator to enter a 6-digit code. READ-ONLY: "
                "cannot submit codes — the operator must enter them manually "
                "via the Accounts page."
            ),
        ),
    )


def register_account_content_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register account-scoped scheduling and discovery read tools."""

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

    def get_post_jobs_handler(args: dict) -> dict:
        return context.postjob_usecases.list_recent_posts(
            limit=args.get("limit", 10),
            status_filter=args.get("status_filter"),
        )

    def schedule_post_handler(args: dict) -> dict:
        return context.postjob_usecases.create_scheduled_post_for_usernames(
            usernames=args.get("usernames", []),
            caption=args.get("caption", ""),
            scheduled_at=args.get("scheduled_at"),
        )

    def get_hashtag_posts_handler(args: dict) -> dict:
        if context.hashtag_use_cases is None:
            return {"error": "Hashtag use cases are not available"}

        username = args.get("username", "").lstrip("@")
        hashtag = args.get("hashtag", "").lstrip("#")
        amount = int(args.get("amount", 12))
        feed = args.get("feed", "recent")

        if not username:
            return {"error": "username is required"}
        if not hashtag:
            return {"error": "hashtag is required"}

        account_id = context.profile_usecases.find_by_username(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}

        try:
            if feed == "top":
                medias = context.hashtag_use_cases.get_hashtag_top_posts(
                    account_id=account_id,
                    name=hashtag,
                    amount=amount,
                )
            else:
                medias = context.hashtag_use_cases.get_hashtag_recent_posts(
                    account_id=account_id,
                    name=hashtag,
                    amount=amount,
                )
        except ValueError as exc:
            return {"error": str(exc)}

        return {
            "hashtag": hashtag,
            "feed": feed,
            "count": len(medias),
            "posts": [_media_to_dict(media) for media in medias],
        }

    def get_collection_posts_handler(args: dict) -> dict:
        if context.collection_use_cases is None:
            return {"error": "Collection use cases are not available"}

        username = args.get("username", "").lstrip("@")
        collection_name = (args.get("collection_name", "") or "").strip()
        amount = int(args.get("amount", 21))
        last_media_pk = int(args.get("last_media_pk", 0))

        if not username:
            return {"error": "username is required"}
        if not collection_name:
            return {"error": "collection_name is required"}

        account_id = context.profile_usecases.find_by_username(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}

        try:
            collection_pk = context.collection_use_cases.get_collection_pk_by_name(
                account_id=account_id,
                name=collection_name,
            )
            medias = context.collection_use_cases.get_collection_posts(
                account_id=account_id,
                collection_pk=collection_pk,
                amount=amount,
                last_media_pk=last_media_pk,
            )
        except ValueError as exc:
            return {"error": str(exc)}

        return {
            "collection": collection_name,
            "collection_pk": collection_pk,
            "count": len(medias),
            "posts": [_media_to_dict(media) for media in medias],
        }

    registry.register(
        "get_post_jobs",
        get_post_jobs_handler,
        schema(
            "get_post_jobs",
            "Get recent post jobs with their status (needs_media, pending, scheduled, running, completed, partial, failed).",
            properties={
                "limit": {
                    "type": "integer",
                    "description": "Number of recent jobs to return (default 10)",
                    "default": 10,
                },
                "status_filter": {
                    "type": "string",
                    "description": "Filter by status: needs_media, pending, scheduled, running, completed, partial, failed, or omit for all",
                },
            },
        ),
    )

    registry.register(
        "schedule_post",
        schedule_post_handler,
        schema(
            "schedule_post",
            "Create a scheduled post job for one or more accounts. The caption will be queued; the operator must attach media via the Post page before the scheduled time.",
            properties={
                "usernames": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Instagram usernames to post to",
                },
                "caption": {
                    "type": "string",
                    "description": "Post caption with hashtags and mentions",
                },
                "scheduled_at": {
                    "type": "string",
                    "description": "ISO 8601 datetime to post e.g. 2026-03-26T15:00:00Z. If omitted, posts immediately.",
                },
            },
            required=["usernames", "caption"],
        ),
    )

    registry.register(
        "get_hashtag_posts",
        get_hashtag_posts_handler,
        schema(
            "get_hashtag_posts",
            "Fetch recent or top posts for a hashtag using authenticated account context.",
            properties={
                "username": {
                    "type": "string",
                    "description": "Instagram username to use as authenticated context",
                },
                "hashtag": {
                    "type": "string",
                    "description": "Hashtag name with or without # prefix",
                },
                "amount": {
                    "type": "integer",
                    "description": "Number of posts to fetch (default 12)",
                    "default": 12,
                },
                "feed": {
                    "type": "string",
                    "description": "Feed type: recent (default) or top",
                    "enum": ["recent", "top"],
                },
            },
            required=["username", "hashtag"],
        ),
    )

    registry.register(
        "get_collection_posts",
        get_collection_posts_handler,
        schema(
            "get_collection_posts",
            "Fetch saved posts from a named collection using authenticated account context.",
            properties={
                "username": {
                    "type": "string",
                    "description": "Instagram username to use as authenticated context",
                },
                "collection_name": {
                    "type": "string",
                    "description": "Collection name (exact name as shown in Instagram saved collections)",
                },
                "amount": {
                    "type": "integer",
                    "description": "Number of posts to fetch (default 21)",
                    "default": 21,
                },
                "last_media_pk": {
                    "type": "integer",
                    "description": "Pagination cursor (last media pk), default 0",
                    "default": 0,
                },
            },
            required=["username", "collection_name"],
        ),
    )
