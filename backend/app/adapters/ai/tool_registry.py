"""AI tool registry - maps tool names to use case handlers."""

from __future__ import annotations

import asyncio
import json
from typing import Callable, Optional


class ToolRegistry:
    """Registry mapping tool names to handler functions."""

    def __init__(self):
        """Initialize with empty registry."""
        self._tools: dict[str, dict[str, object]] = {}
        self._schemas: list[dict] = []

    def register(
        self,
        name: str,
        handler: Callable[[dict], dict],
        schema: dict,
    ) -> None:
        """Register a tool.

        Args:
            name: Tool name
            handler: Sync or async function(args) -> dict
            schema: OpenAI function schema
        """
        self._tools[name] = {
            "handler": handler,
            "schema": schema,
        }
        self._schemas.append(schema)

    def get_schemas(self) -> list[dict]:
        """Get all tool schemas for AI provider."""
        return self._schemas

    async def execute(self, name: str, args: dict) -> dict:
        """Execute a tool by name.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            Tool result dict

        Raises:
            ValueError: If tool not found
        """
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"Unknown tool: {name}"}

        handler = tool["handler"]

        # Run handler (sync or async)
        try:
            if asyncio.iscoroutinefunction(handler):
                return await handler(args)
            else:
                # Run sync handler in thread pool to avoid blocking
                return await asyncio.to_thread(handler, args)
        except Exception as e:
            return {"error": str(e)}


def _schema(
    name: str,
    description: str,
    properties: dict | None = None,
    required: list[str] | None = None,
) -> dict:
    """Build OpenAI function schema."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


def create_tool_registry(
    account_usecases,
    postjob_usecases,
    hashtag_use_cases=None,
    collection_use_cases=None,
    media_use_cases=None,
    story_use_cases=None,
    highlight_use_cases=None,
    comment_use_cases=None,
    direct_use_cases=None,
    insight_use_cases=None,
    relationship_use_cases=None,
    account_profile_usecases=None,
    account_auth_usecases=None,
    account_proxy_usecases=None,
    proxy_pool_usecases=None,
) -> ToolRegistry:
    """Create and populate tool registry from use cases.

    Args:
        account_usecases: Account use cases instance
        postjob_usecases: Post job use cases instance
        hashtag_use_cases: Optional HashtagUseCases instance
        collection_use_cases: Optional CollectionUseCases instance
        media_use_cases: Optional MediaUseCases instance
        story_use_cases: Optional StoryUseCases instance
        highlight_use_cases: Optional HighlightUseCases instance
        comment_use_cases: Optional CommentUseCases instance
        direct_use_cases: Optional DirectUseCases instance
        insight_use_cases: Optional InsightUseCases instance
        relationship_use_cases: Optional RelationshipUseCases instance

    Returns:
        Populated ToolRegistry
    """
    registry = ToolRegistry()

    # Prefer split use cases when available, fall back to monolith
    _profile = account_profile_usecases or account_usecases
    _auth = account_auth_usecases or account_usecases
    _proxy = account_proxy_usecases or account_usecases

    # Tool handlers - wrap use cases
    def list_accounts_handler(_args: dict) -> dict:
        return _profile.get_accounts_summary()

    def _resolve_account_from_args(args: dict) -> tuple[Optional[str], Optional[str]]:
        username = str(args.get("username") or args.get("account_name") or "").strip().lstrip("@")
        if username:
            account_id = _profile.find_by_username(username)
            if account_id:
                return account_id, None
            return None, f"Account @{username} not found"

        account_id = str(args.get("account_id") or "").strip()
        if account_id:
            account = getattr(_profile, "account_repo", None)
            account_data = account.get(account_id) if account is not None else None
            if account_data:
                return account_id, None
            return None, f"Account id {account_id} not found"

        return None, "username is required"

    def get_account_info_handler(args: dict) -> dict:
        account_id, error = _resolve_account_from_args(args)
        if not account_id:
            return {"error": error}

        result = _profile.get_account_info(account_id)
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
        return _auth.relogin_account_by_username(username)

    def logout_account_handler(args: dict) -> dict:
        account_id, error = _resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        username = args.get("username", "").lstrip("@")
        try:
            _auth.logout_account(account_id, detail="ai_tool")
        except ValueError as exc:
            return {"error": str(exc)}
        return {"success": True, "message": f"@{username} logged out and removed"}

    def set_account_proxy_handler(args: dict) -> dict:
        username = args.get("username", "").lstrip("@")
        proxy_url = args.get("proxy_url", "")
        account_id = _profile.find_by_username(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            _proxy.set_account_proxy(account_id, proxy_url)
        except ValueError as exc:
            return {"error": str(exc)}
        return {
            "success": True,
            "username": username,
            "proxy": proxy_url,
            "message": f"Proxy updated for @{username}",
        }

    def get_post_jobs_handler(args: dict) -> dict:
        return postjob_usecases.list_recent_posts(
            limit=args.get("limit", 10),
            status_filter=args.get("status_filter"),
        )

    def schedule_post_handler(args: dict) -> dict:
        return postjob_usecases.create_scheduled_post_for_usernames(
            usernames=args.get("usernames", []),
            caption=args.get("caption", ""),
            scheduled_at=args.get("scheduled_at"),
        )

    def get_hashtag_posts_handler(args: dict) -> dict:
        if hashtag_use_cases is None:
            return {"error": "Hashtag use cases are not available"}

        username = args.get("username", "").lstrip("@")
        hashtag = args.get("hashtag", "").lstrip("#")
        amount = int(args.get("amount", 12))
        feed = args.get("feed", "recent")

        if not username:
            return {"error": "username is required"}
        if not hashtag:
            return {"error": "hashtag is required"}

        account_id = _profile.find_by_username(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}

        try:
            if feed == "top":
                medias = hashtag_use_cases.get_hashtag_top_posts(
                    account_id=account_id,
                    name=hashtag,
                    amount=amount,
                )
            else:
                medias = hashtag_use_cases.get_hashtag_recent_posts(
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
            "posts": [
                {
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
                for media in medias
            ],
        }

    def get_collection_posts_handler(args: dict) -> dict:
        if collection_use_cases is None:
            return {"error": "Collection use cases are not available"}

        username = args.get("username", "").lstrip("@")
        collection_name = (args.get("collection_name", "") or "").strip()
        amount = int(args.get("amount", 21))
        last_media_pk = int(args.get("last_media_pk", 0))

        if not username:
            return {"error": "username is required"}
        if not collection_name:
            return {"error": "collection_name is required"}

        account_id = _profile.find_by_username(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}

        try:
            collection_pk = collection_use_cases.get_collection_pk_by_name(
                account_id=account_id,
                name=collection_name,
            )
            medias = collection_use_cases.get_collection_posts(
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
            "posts": [
                {
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
                for media in medias
            ],
        }

    # Register tools
    registry.register(
        "list_accounts",
        list_accounts_handler,
        _schema(
            "list_accounts",
            "List all Instagram accounts managed in this system with their current status, followers, following counts, and proxy settings.",
        ),
    )

    registry.register(
        "get_account_info",
        get_account_info_handler,
        _schema(
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
        _schema(
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
        _schema(
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
        _schema(
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

    async def check_proxy_handler(args: dict) -> dict:
        proxy_url = args.get("proxy_url", "")
        if not proxy_url:
            return {"error": "proxy_url is required"}
        result = await _proxy.check_proxy(proxy_url)
        return {
            "proxy_url": result.proxy_url,
            "reachable": result.reachable,
            "latency_ms": result.latency_ms,
            "ip_address": result.ip_address,
            "error": result.error,
            "status": "ok" if result.reachable else "failed",
        }

    registry.register(
        "check_proxy",
        check_proxy_handler,
        _schema(
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

    # ── Proxy pool tools ───────────────────────────────────────────────────────

    def _proxy_to_dict(p) -> dict:
        return {
            "host": p.host,
            "port": p.port,
            "protocol": p.protocol,
            "anonymity": p.anonymity,
            "latency_ms": p.latency_ms,
            "url": p.url,
        }

    def list_proxy_pool_handler(_args: dict) -> dict:
        if proxy_pool_usecases is None:
            return {"error": "Proxy pool use cases not available"}
        proxies = proxy_pool_usecases.list_proxies()
        return {"count": len(proxies), "proxies": [_proxy_to_dict(p) for p in proxies]}

    async def import_proxies_handler(args: dict) -> dict:
        if proxy_pool_usecases is None:
            return {"error": "Proxy pool use cases not available"}
        text = args.get("text", "")
        if not text.strip():
            return {"error": "text is required"}
        summary = await proxy_pool_usecases.import_from_text(text)
        return {
            "total": summary.total,
            "saved": summary.saved,
            "skipped_transparent": summary.skipped_transparent,
            "skipped_duplicate": summary.skipped_duplicate,
            "skipped_existing": summary.skipped_existing,
            "failed": summary.failed,
            "errors": summary.errors[:10],
        }

    async def recheck_proxy_pool_handler(_args: dict) -> dict:
        if proxy_pool_usecases is None:
            return {"error": "Proxy pool use cases not available"}
        summary = await proxy_pool_usecases.recheck_pool()
        return {
            "total": summary.total,
            "alive": summary.alive,
            "removed": summary.removed,
        }

    def delete_proxy_handler(args: dict) -> dict:
        if proxy_pool_usecases is None:
            return {"error": "Proxy pool use cases not available"}
        host = args.get("host", "")
        port = args.get("port")
        if not host:
            return {"error": "host is required"}
        if port is None:
            return {"error": "port is required"}
        try:
            proxy_pool_usecases.delete_proxy(host, int(port))
            return {"success": True, "deleted": f"{host}:{port}"}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def pick_proxy_handler(_args: dict) -> dict:
        if proxy_pool_usecases is None:
            return {"error": "Proxy pool use cases not available"}
        url = proxy_pool_usecases.pick_proxy()
        if url is None:
            return {"proxy_url": None, "message": "No working proxies available in pool"}
        return {"proxy_url": url}

    registry.register(
        "list_proxy_pool",
        list_proxy_pool_handler,
        _schema(
            "list_proxy_pool",
            "List all proxies in the proxy pool with their status and latency.",
            properties={},
            required=[],
        ),
    )

    registry.register(
        "import_proxies",
        import_proxies_handler,
        _schema(
            "import_proxies",
            "Import proxies from a newline-separated text list. Each line should be a proxy URL (e.g. http://user:pass@host:port).",
            properties={
                "text": {"type": "string", "description": "Newline-separated list of proxy URLs to import"},
            },
            required=["text"],
        ),
    )

    registry.register(
        "recheck_proxy_pool",
        recheck_proxy_pool_handler,
        _schema(
            "recheck_proxy_pool",
            "Re-test all proxies in the pool. Removes dead proxies and updates latency for alive ones.",
            properties={},
            required=[],
        ),
    )

    registry.register(
        "delete_proxy",
        delete_proxy_handler,
        _schema(
            "delete_proxy",
            "Delete a proxy from the pool by host and port.",
            properties={
                "host": {"type": "string", "description": "Proxy host/IP"},
                "port": {"type": "integer", "description": "Proxy port"},
            },
            required=["host", "port"],
        ),
    )

    registry.register(
        "pick_proxy",
        pick_proxy_handler,
        _schema(
            "pick_proxy",
            "Pick a random working proxy from the pool.",
            properties={},
            required=[],
        ),
    )

    registry.register(
        "get_post_jobs",
        get_post_jobs_handler,
        _schema(
            "get_post_jobs",
            "Get recent post jobs with their status (pending, scheduled, running, completed, partial, failed).",
            properties={
                "limit": {
                    "type": "integer",
                    "description": "Number of recent jobs to return (default 10)",
                    "default": 10,
                },
                "status_filter": {
                    "type": "string",
                    "description": "Filter by status: pending, scheduled, running, completed, partial, failed, or omit for all",
                },
            },
        ),
    )

    registry.register(
        "schedule_post",
        schedule_post_handler,
        _schema(
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
        _schema(
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
        _schema(
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

    # ── Media tools ────────────────────────────────────────────────────────────

    def _resolve_account(username: str) -> Optional[str]:
        """Return account_id or None. Explicit empty-string guard prevents
        ambiguous '@' lookup — callers that need a descriptive error should
        check for empty username before calling."""
        uname = (username or "").lstrip("@")
        if not uname:
            return None
        return _profile.find_by_username(uname)

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

    def get_media_by_pk_handler(args: dict) -> dict:
        if media_use_cases is None:
            return {"error": "Media use cases not available"}
        account_id, error = _resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            media = media_use_cases.get_media_by_pk(account_id, int(args["media_pk"]))
            return _media_to_dict(media)
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def get_media_by_code_handler(args: dict) -> dict:
        if media_use_cases is None:
            return {"error": "Media use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            media = media_use_cases.get_media_by_code(account_id, args["code"])
            return _media_to_dict(media)
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def get_user_medias_handler(args: dict) -> dict:
        if media_use_cases is None:
            return {"error": "Media use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            medias = media_use_cases.get_user_medias(
                account_id, int(args["user_id"]), amount=int(args.get("amount", 12))
            )
            return {"count": len(medias), "posts": [_media_to_dict(m) for m in medias]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "get_media_by_pk",
        get_media_by_pk_handler,
        _schema(
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
        _schema(
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
        _schema(
            "get_user_medias",
            "List recent posts for an Instagram user by their numeric user ID.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "user_id": {"type": "integer", "description": "Numeric Instagram user ID"},
                "amount": {"type": "integer", "description": "Number of posts to fetch (default 12)", "default": 12},
            },
            required=["username", "user_id"],
        ),
    )

    # ── Story tools ────────────────────────────────────────────────────────────

    def _story_summary_to_dict(s) -> dict:
        return {
            "pk": s.pk,
            "story_id": s.story_id,
            "media_type": s.media_type,
            "taken_at": s.taken_at.isoformat() if s.taken_at else None,
            "thumbnail_url": s.thumbnail_url,
            "owner_username": s.owner_username,
        }

    def list_user_stories_handler(args: dict) -> dict:
        if story_use_cases is None:
            return {"error": "Story use cases not available"}
        account_id, error = _resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            stories = story_use_cases.list_user_stories(
                account_id, int(args["user_id"]), amount=args.get("amount")
            )
            return {"count": len(stories), "stories": [_story_summary_to_dict(s) for s in stories]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "list_user_stories",
        list_user_stories_handler,
        _schema(
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

    # ── Highlight tools ────────────────────────────────────────────────────────

    def _highlight_summary_to_dict(h) -> dict:
        return {
            "pk": h.pk,
            "highlight_id": h.highlight_id,
            "title": h.title,
            "media_count": h.media_count,
            "owner_username": h.owner_username,
        }

    def list_user_highlights_handler(args: dict) -> dict:
        if highlight_use_cases is None:
            return {"error": "Highlight use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            highlights = highlight_use_cases.list_user_highlights(
                account_id, int(args["user_id"])
            )
            return {"count": len(highlights), "highlights": [_highlight_summary_to_dict(h) for h in highlights]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def create_highlight_handler(args: dict) -> dict:
        if highlight_use_cases is None:
            return {"error": "Highlight use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = highlight_use_cases.create_highlight(
                account_id,
                title=args["title"],
                story_ids=[int(x) for x in args.get("story_ids", [])],
            )
            return {"success": True, "highlight": _highlight_summary_to_dict(result.summary)}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def delete_highlight_handler(args: dict) -> dict:
        if highlight_use_cases is None:
            return {"error": "Highlight use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = highlight_use_cases.delete_highlight(account_id, int(args["highlight_pk"]))
            return {"success": result.success, "reason": result.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "list_user_highlights",
        list_user_highlights_handler,
        _schema(
            "list_user_highlights",
            "List all Instagram story highlights for a user by their numeric user ID.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "user_id": {"type": "integer", "description": "Numeric Instagram user ID"},
            },
            required=["username", "user_id"],
        ),
    )

    registry.register(
        "create_highlight",
        create_highlight_handler,
        _schema(
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
        _schema(
            "delete_highlight",
            "Delete a story highlight by its numeric pk.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "highlight_pk": {"type": "integer", "description": "Numeric highlight ID"},
            },
            required=["username", "highlight_pk"],
        ),
    )

    # ── Comment tools ──────────────────────────────────────────────────────────

    def _comment_to_dict(c) -> dict:
        return {
            "pk": c.pk,
            "text": c.text,
            "author": c.author.username if c.author else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "like_count": c.like_count,
        }

    def list_comments_handler(args: dict) -> dict:
        if comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            comments = comment_use_cases.list_comments(
                account_id, args["media_id"], amount=int(args.get("amount", 0))
            )
            return {"count": len(comments), "comments": [_comment_to_dict(c) for c in comments]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def create_comment_handler(args: dict) -> dict:
        if comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            comment = comment_use_cases.create_comment(
                account_id, args["media_id"], args["text"],
                reply_to_comment_id=args.get("reply_to_comment_id"),
            )
            return {"success": True, "comment": _comment_to_dict(comment)}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def delete_comment_handler(args: dict) -> dict:
        if comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = comment_use_cases.delete_comment(
                account_id, args["media_id"], int(args["comment_id"])
            )
            return {"success": result.success, "reason": result.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "list_comments",
        list_comments_handler,
        _schema(
            "list_comments",
            "Fetch comments on an Instagram post by its media ID.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "media_id": {"type": "string", "description": "Instagram media ID"},
                "amount": {"type": "integer", "description": "Max comments to fetch (default all)", "default": 0},
            },
            required=["username", "media_id"],
        ),
    )

    registry.register(
        "create_comment",
        create_comment_handler,
        _schema(
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
        _schema(
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

    def like_comment_handler(args: dict) -> dict:
        if comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = comment_use_cases.like_comment(account_id, int(args["comment_id"]))
            return {"success": result.success, "reason": result.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def unlike_comment_handler(args: dict) -> dict:
        if comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = comment_use_cases.unlike_comment(account_id, int(args["comment_id"]))
            return {"success": result.success, "reason": result.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def pin_comment_handler(args: dict) -> dict:
        if comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = comment_use_cases.pin_comment(
                account_id, args["media_id"], int(args["comment_id"])
            )
            return {"success": result.success, "reason": result.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def unpin_comment_handler(args: dict) -> dict:
        if comment_use_cases is None:
            return {"error": "Comment use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            result = comment_use_cases.unpin_comment(
                account_id, args["media_id"], int(args["comment_id"])
            )
            return {"success": result.success, "reason": result.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "like_comment",
        like_comment_handler,
        _schema(
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
        _schema(
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
        _schema(
            "pin_comment",
            "Pin a comment on a post owned by the account. Only works on own posts.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "media_id": {"type": "string", "description": "Instagram media ID (must be owned by account)"},
                "comment_id": {"type": "integer", "description": "Numeric comment ID to pin"},
            },
            required=["username", "media_id", "comment_id"],
        ),
    )

    registry.register(
        "unpin_comment",
        unpin_comment_handler,
        _schema(
            "unpin_comment",
            "Unpin a pinned comment on a post owned by the account.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "media_id": {"type": "string", "description": "Instagram media ID (must be owned by account)"},
                "comment_id": {"type": "integer", "description": "Numeric comment ID to unpin"},
            },
            required=["username", "media_id", "comment_id"],
        ),
    )

    # ── Direct message tools ───────────────────────────────────────────────────

    def _thread_to_dict(t) -> dict:
        return {
            "thread_id": t.direct_thread_id,
            "participants": [p.username for p in (t.participants or [])],
            "is_pending": t.is_pending,
            "last_message": t.last_message.text if t.last_message else None,
        }

    def list_inbox_threads_handler(args: dict) -> dict:
        if direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            threads = direct_use_cases.list_inbox_threads(
                account_id, amount=int(args.get("amount", 20))
            )
            return {"count": len(threads), "threads": [_thread_to_dict(t) for t in threads]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def list_pending_threads_handler(args: dict) -> dict:
        if direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            threads = direct_use_cases.list_pending_threads(
                account_id, amount=int(args.get("amount", 20))
            )
            return {"count": len(threads), "threads": [_thread_to_dict(t) for t in threads]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def search_threads_handler(args: dict) -> dict:
        if direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            threads = direct_use_cases.search_threads(account_id, args["query"])
            return {"count": len(threads), "threads": [_thread_to_dict(t) for t in threads]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def send_direct_message_handler(args: dict) -> dict:
        if direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        recipient = args.get("recipient_username", "").lstrip("@")
        text = args.get("text", "")
        if not recipient:
            return {"error": "recipient_username is required"}
        if not text:
            return {"error": "text is required"}
        try:
            msg = direct_use_cases.send_to_username(account_id, recipient, text)
            return {
                "success": True,
                "thread_id": msg.direct_thread_id,
                "message_id": msg.direct_message_id,
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "list_inbox_threads",
        list_inbox_threads_handler,
        _schema(
            "list_inbox_threads",
            "List direct message inbox threads for an account.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "amount": {"type": "integer", "description": "Number of threads to return (default 20)", "default": 20},
            },
            required=["username"],
        ),
    )

    registry.register(
        "list_pending_threads",
        list_pending_threads_handler,
        _schema(
            "list_pending_threads",
            "List pending (unaccepted) direct message requests for an account.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "amount": {"type": "integer", "description": "Number of threads to return (default 20)", "default": 20},
            },
            required=["username"],
        ),
    )

    registry.register(
        "search_threads",
        search_threads_handler,
        _schema(
            "search_threads",
            "Search direct message threads by participant username or keyword.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "query": {"type": "string", "description": "Search query (username or keyword)"},
            },
            required=["username", "query"],
        ),
    )

    registry.register(
        "send_direct_message",
        send_direct_message_handler,
        _schema(
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

    def _message_to_dict(m) -> dict:
        return {
            "message_id": m.direct_message_id,
            "thread_id": m.direct_thread_id,
            "sender_user_id": m.sender_user_id,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            "item_type": m.item_type,
            "text": m.text,
        }

    def get_thread_handler(args: dict) -> dict:
        if direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            detail = direct_use_cases.get_thread(
                account_id,
                args["thread_id"],
                amount=int(args.get("amount", 20)),
            )
            return {
                **_thread_to_dict(detail.summary),
                "messages": [_message_to_dict(m) for m in detail.messages],
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def list_messages_handler(args: dict) -> dict:
        if direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        try:
            messages = direct_use_cases.list_messages(
                account_id,
                args["thread_id"],
                amount=int(args.get("amount", 20)),
            )
            return {"count": len(messages), "messages": [_message_to_dict(m) for m in messages]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def send_to_thread_handler(args: dict) -> dict:
        if direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        thread_id = args.get("thread_id", "")
        text = args.get("text", "")
        if not thread_id:
            return {"error": "thread_id is required"}
        if not text:
            return {"error": "text is required"}
        try:
            msg = direct_use_cases.send_to_thread(account_id, thread_id, text)
            return {
                "success": True,
                "thread_id": msg.direct_thread_id,
                "message_id": msg.direct_message_id,
            }
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def find_or_create_thread_handler(args: dict) -> dict:
        if direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        usernames = [u.lstrip("@") for u in args.get("participant_usernames", []) if u]
        if not usernames:
            return {"error": "participant_usernames is required and must not be empty"}
        try:
            thread = direct_use_cases.find_or_create_thread_with_usernames(account_id, usernames)
            return _thread_to_dict(thread)
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def delete_message_handler(args: dict) -> dict:
        if direct_use_cases is None:
            return {"error": "Direct use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        thread_id = args.get("thread_id", "")
        message_id = args.get("message_id", "")
        if not thread_id:
            return {"error": "thread_id is required"}
        if not message_id:
            return {"error": "message_id is required"}
        try:
            receipt = direct_use_cases.delete_message(account_id, thread_id, message_id)
            return {"success": receipt.success, "reason": receipt.reason}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "get_direct_thread",
        get_thread_handler,
        _schema(
            "get_direct_thread",
            "Get a specific direct message thread with its messages.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "thread_id": {"type": "string", "description": "Direct thread ID"},
                "amount": {"type": "integer", "description": "Number of messages to retrieve (default 20)", "default": 20},
            },
            required=["username", "thread_id"],
        ),
    )

    registry.register(
        "list_direct_messages",
        list_messages_handler,
        _schema(
            "list_direct_messages",
            "List messages in a direct message thread.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "thread_id": {"type": "string", "description": "Direct thread ID"},
                "amount": {"type": "integer", "description": "Number of messages to retrieve (default 20)", "default": 20},
            },
            required=["username", "thread_id"],
        ),
    )

    registry.register(
        "send_message_to_thread",
        send_to_thread_handler,
        _schema(
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
        _schema(
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
        _schema(
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

    # ── Insight tools ──────────────────────────────────────────────────────────

    def _insight_to_dict(ins) -> dict:
        return {
            "media_pk": ins.media_pk,
            "reach_count": ins.reach_count,
            "impression_count": ins.impression_count,
            "like_count": ins.like_count,
            "comment_count": ins.comment_count,
            "share_count": ins.share_count,
            "save_count": ins.save_count,
            "video_view_count": ins.video_view_count,
        }

    def get_media_insight_handler(args: dict) -> dict:
        if insight_use_cases is None:
            return {"error": "Insight use cases not available"}
        account_id, error = _resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            ins = insight_use_cases.get_media_insight(account_id, int(args["media_pk"]))
            return _insight_to_dict(ins)
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def list_media_insights_handler(args: dict) -> dict:
        if insight_use_cases is None:
            return {"error": "Insight use cases not available"}
        account_id, error = _resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        try:
            results = insight_use_cases.list_media_insights(
                account_id,
                post_type=args.get("post_type", "ALL"),
                time_frame=args.get("time_frame", "TWO_YEARS"),
                ordering=args.get("ordering", "REACH_COUNT"),
                count=int(args.get("count", 0)),
            )
            return {"count": len(results), "insights": [_insight_to_dict(ins) for ins in results]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "get_media_insight",
        get_media_insight_handler,
        _schema(
            "get_media_insight",
            "Get detailed analytics for a single post: reach, impressions, likes, comments, shares, saves.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username (must own the post)"},
                "media_pk": {"type": "integer", "description": "Numeric post ID"},
            },
            required=["username", "media_pk"],
        ),
    )

    registry.register(
        "list_media_insights",
        list_media_insights_handler,
        _schema(
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
                    "enum": ["REACH_COUNT", "IMPRESSIONS", "ENGAGEMENT", "LIKE_COUNT", "COMMENT_COUNT", "SHARE_COUNT", "SAVE_COUNT"],
                    "default": "REACH_COUNT",
                },
                "count": {"type": "integer", "description": "Max posts to return (default all)", "default": 0},
            },
            required=["username"],
        ),
    )

    # ── Relationship write tools ───────────────────────────────────────────────

    def follow_user_handler(args: dict) -> dict:
        if relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        account_id, error = _resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        target = args.get("target_username", "").lstrip("@")
        if not target:
            return {"error": "target_username is required"}
        try:
            success = relationship_use_cases.follow_user(account_id, target)
            return {"success": success, "action": "follow", "target": target}
        except ValueError as exc:
            return {"error": str(exc)}

    def unfollow_user_handler(args: dict) -> dict:
        if relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        target = args.get("target_username", "").lstrip("@")
        if not target:
            return {"error": "target_username is required"}
        try:
            success = relationship_use_cases.unfollow_user(account_id, target)
            return {"success": success, "action": "unfollow", "target": target}
        except ValueError as exc:
            return {"error": str(exc)}

    registry.register(
        "follow_user",
        follow_user_handler,
        _schema(
            "follow_user",
            "Follow an Instagram user. Requires operator approval before execution.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username performing the follow"},
                "target_username": {"type": "string", "description": "Instagram username to follow"},
            },
            required=["username", "target_username"],
        ),
    )

    registry.register(
        "unfollow_user",
        unfollow_user_handler,
        _schema(
            "unfollow_user",
            "Unfollow an Instagram user. Requires operator approval before execution.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username performing the unfollow"},
                "target_username": {"type": "string", "description": "Instagram username to unfollow"},
            },
            required=["username", "target_username"],
        ),
    )

    def _profile_to_dict(p) -> dict:
        return {
            "user_id": p.pk,
            "username": p.username,
            "full_name": p.full_name,
            "follower_count": p.follower_count,
            "following_count": p.following_count,
            "is_private": p.is_private,
            "is_verified": p.is_verified,
        }

    def list_followers_handler(args: dict) -> dict:
        if relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        target = args.get("target_username", username).lstrip("@")
        try:
            followers = relationship_use_cases.list_followers(
                account_id, target, amount=int(args.get("amount", 50))
            )
            return {"count": len(followers), "followers": [_profile_to_dict(p) for p in followers]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def list_following_handler(args: dict) -> dict:
        if relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        target = args.get("target_username", username).lstrip("@")
        try:
            following = relationship_use_cases.list_following(
                account_id, target, amount=int(args.get("amount", 50))
            )
            return {"count": len(following), "following": [_profile_to_dict(p) for p in following]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "list_followers",
        list_followers_handler,
        _schema(
            "list_followers",
            "List followers of an Instagram account.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "target_username": {"type": "string", "description": "Username whose followers to list (defaults to authenticated account)"},
                "amount": {"type": "integer", "description": "Number of followers to return (default 50)", "default": 50},
            },
            required=["username"],
        ),
    )

    registry.register(
        "list_following",
        list_following_handler,
        _schema(
            "list_following",
            "List accounts followed by an Instagram account.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "target_username": {"type": "string", "description": "Username whose following list to retrieve (defaults to authenticated account)"},
                "amount": {"type": "integer", "description": "Number of following accounts to return (default 50)", "default": 50},
            },
            required=["username"],
        ),
    )

    # ── Relationship search tools ──────────���──────────────────────────────────

    def search_followers_handler(args: dict) -> dict:
        if relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        target = args.get("target_username", username).lstrip("@")
        query = args.get("query", "")
        if not query:
            return {"error": "query is required"}
        try:
            results = relationship_use_cases.search_followers(account_id, target, query=query)
            return {"count": len(results), "followers": [_profile_to_dict(p) for p in results]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def search_following_handler(args: dict) -> dict:
        if relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        target = args.get("target_username", username).lstrip("@")
        query = args.get("query", "")
        if not query:
            return {"error": "query is required"}
        try:
            results = relationship_use_cases.search_following(account_id, target, query=query)
            return {"count": len(results), "following": [_profile_to_dict(p) for p in results]}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    registry.register(
        "search_followers",
        search_followers_handler,
        _schema(
            "search_followers",
            "Search within an Instagram user's follower list by keyword.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "target_username": {"type": "string", "description": "Username whose followers to search (defaults to authenticated account)"},
                "query": {"type": "string", "description": "Search query string"},
            },
            required=["username", "query"],
        ),
    )

    registry.register(
        "search_following",
        search_following_handler,
        _schema(
            "search_following",
            "Search within an Instagram user's following list by keyword.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "target_username": {"type": "string", "description": "Username whose following to search (defaults to authenticated account)"},
                "query": {"type": "string", "description": "Search query string"},
            },
            required=["username", "query"],
        ),
    )

    # ── Relationship management tools ──────────���────────────────────────────

    def remove_follower_handler(args: dict) -> dict:
        if relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        account_id, error = _resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        target = args.get("target_username", "").lstrip("@")
        if not target:
            return {"error": "target_username is required"}
        try:
            success = relationship_use_cases.remove_follower(account_id, target)
            return {"success": success, "action": "remove_follower", "target": target}
        except ValueError as exc:
            return {"error": str(exc)}

    def close_friend_add_handler(args: dict) -> dict:
        if relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        account_id, error = _resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        target = args.get("target_username", "").lstrip("@")
        if not target:
            return {"error": "target_username is required"}
        try:
            success = relationship_use_cases.close_friend_add(account_id, target)
            return {"success": success, "action": "close_friend_add", "target": target}
        except ValueError as exc:
            return {"error": str(exc)}

    def close_friend_remove_handler(args: dict) -> dict:
        if relationship_use_cases is None:
            return {"error": "Relationship use cases not available"}
        account_id, error = _resolve_account_from_args(args)
        if not account_id:
            return {"error": error}
        target = args.get("target_username", "").lstrip("@")
        if not target:
            return {"error": "target_username is required"}
        try:
            success = relationship_use_cases.close_friend_remove(account_id, target)
            return {"success": success, "action": "close_friend_remove", "target": target}
        except ValueError as exc:
            return {"error": str(exc)}

    registry.register(
        "remove_follower",
        remove_follower_handler,
        _schema(
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
        _schema(
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
        _schema(
            "close_friend_remove",
            "Remove a user from the Close Friends list. Requires operator approval.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username"},
                "target_username": {"type": "string", "description": "Username to remove from Close Friends"},
            },
            required=["username", "target_username"],
        ),
    )

    # ── Media write tools ──────────────────────────────────────────────────────

    def like_post_handler(args: dict) -> dict:
        if media_use_cases is None:
            return {"error": "Media use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        media_id = args.get("media_id", "")
        if not media_id:
            return {"error": "media_id is required"}
        try:
            success = media_use_cases.like_media(account_id, media_id)
            return {"success": success, "action": "like", "media_id": media_id}
        except ValueError as exc:
            return {"error": str(exc)}

    def unlike_post_handler(args: dict) -> dict:
        if media_use_cases is None:
            return {"error": "Media use cases not available"}
        username = args.get("username", "")
        account_id = _resolve_account(username)
        if not account_id:
            return {"error": f"Account @{username} not found"}
        media_id = args.get("media_id", "")
        if not media_id:
            return {"error": "media_id is required"}
        try:
            success = media_use_cases.unlike_media(account_id, media_id)
            return {"success": success, "action": "unlike", "media_id": media_id}
        except ValueError as exc:
            return {"error": str(exc)}

    registry.register(
        "like_post",
        like_post_handler,
        _schema(
            "like_post",
            "Like an Instagram post. Requires operator approval before execution.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username performing the like"},
                "media_id": {"type": "string", "description": "Instagram media ID string (e.g. '3488123456_25025320')"},
            },
            required=["username", "media_id"],
        ),
    )

    registry.register(
        "unlike_post",
        unlike_post_handler,
        _schema(
            "unlike_post",
            "Remove a like from an Instagram post. Requires operator approval before execution.",
            properties={
                "username": {"type": "string", "description": "Authenticated account username removing the like"},
                "media_id": {"type": "string", "description": "Instagram media ID string"},
            },
            required=["username", "media_id"],
        ),
    )

    return registry
