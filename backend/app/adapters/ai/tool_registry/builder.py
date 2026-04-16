"""Composition root for AI tool registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .account_tools import register_account_content_tools, register_account_tools
from .content_read_tools import (
    register_comment_read_tools,
    register_discovery_read_tools,
    register_direct_inbox_read_tools,
    register_direct_thread_read_tools,
    register_highlight_read_tools,
    register_insight_read_tools,
    register_media_read_tools,
    register_relationship_read_tools,
    register_story_read_tools,
)
from .core import ToolRegistry
from .engagement_write_tools import (
    register_comment_write_tools,
    register_direct_attachment_write_tools,
    register_direct_thread_write_tools,
    register_highlight_write_tools,
    register_media_write_tools,
    register_relationship_management_write_tools,
    register_relationship_primary_write_tools,
    register_send_direct_message_tool,
    register_story_write_tools,
)
from .proxy_pool_tools import register_proxy_pool_tools


@dataclass(slots=True)
class ToolBuilderContext:
    """Shared use-case dependencies and account helpers for tool packs."""

    account_usecases: Any
    postjob_usecases: Any
    hashtag_use_cases: Any = None
    collection_use_cases: Any = None
    media_use_cases: Any = None
    story_use_cases: Any = None
    highlight_use_cases: Any = None
    comment_use_cases: Any = None
    direct_use_cases: Any = None
    insight_use_cases: Any = None
    relationship_use_cases: Any = None
    account_profile_usecases: Any = None
    account_auth_usecases: Any = None
    account_proxy_usecases: Any = None
    account_edit_usecases: Any = None
    account_challenge_usecases: Any = None
    proxy_pool_usecases: Any = None

    profile_usecases: Any = field(init=False)
    auth_usecases: Any = field(init=False)
    proxy_usecases: Any = field(init=False)
    edit_usecases: Any = field(init=False)
    challenge_usecases: Any = field(init=False)

    def __post_init__(self) -> None:
        # Prefer split use cases when available, fall back to monolith.
        self.profile_usecases = self.account_profile_usecases or self.account_usecases
        self.auth_usecases = self.account_auth_usecases or self.account_usecases
        self.proxy_usecases = self.account_proxy_usecases or self.account_usecases
        self.edit_usecases = self.account_edit_usecases
        self.challenge_usecases = self.account_challenge_usecases

    def resolve_account_from_args(self, args: dict) -> tuple[Optional[str], Optional[str]]:
        username = str(args.get("username") or args.get("account_name") or "").strip().lstrip("@")
        if username:
            account_id = self.profile_usecases.find_by_username(username)
            if account_id:
                return account_id, None
            return None, f"Account @{username} not found"

        account_id = str(args.get("account_id") or "").strip()
        if account_id:
            account = getattr(self.profile_usecases, "account_repo", None)
            account_data = account.get(account_id) if account is not None else None
            if account_data:
                return account_id, None
            return None, f"Account id {account_id} not found"

        return None, "username is required"

    def resolve_account(self, username: str) -> Optional[str]:
        """Return account_id or None for a username."""
        uname = (username or "").lstrip("@")
        if not uname:
            return None
        return self.profile_usecases.find_by_username(uname)


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
    account_edit_usecases=None,
    account_challenge_usecases=None,
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
    context = ToolBuilderContext(
        account_usecases=account_usecases,
        postjob_usecases=postjob_usecases,
        hashtag_use_cases=hashtag_use_cases,
        collection_use_cases=collection_use_cases,
        media_use_cases=media_use_cases,
        story_use_cases=story_use_cases,
        highlight_use_cases=highlight_use_cases,
        comment_use_cases=comment_use_cases,
        direct_use_cases=direct_use_cases,
        insight_use_cases=insight_use_cases,
        relationship_use_cases=relationship_use_cases,
        account_profile_usecases=account_profile_usecases,
        account_auth_usecases=account_auth_usecases,
        account_proxy_usecases=account_proxy_usecases,
        account_edit_usecases=account_edit_usecases,
        account_challenge_usecases=account_challenge_usecases,
        proxy_pool_usecases=proxy_pool_usecases,
    )

    # Keep registration order stable to preserve tool schema ordering behavior.
    register_account_tools(registry, context)
    register_proxy_pool_tools(registry, context)
    register_account_content_tools(registry, context)

    register_discovery_read_tools(registry, context)
    register_media_read_tools(registry, context)
    register_story_read_tools(registry, context)
    register_highlight_read_tools(registry, context)

    register_story_write_tools(registry, context)
    register_highlight_write_tools(registry, context)

    register_comment_read_tools(registry, context)
    register_comment_write_tools(registry, context)

    register_direct_inbox_read_tools(registry, context)
    register_send_direct_message_tool(registry, context)
    register_direct_thread_read_tools(registry, context)
    register_direct_thread_write_tools(registry, context)
    register_direct_attachment_write_tools(registry, context)

    register_insight_read_tools(registry, context)

    register_relationship_primary_write_tools(registry, context)
    register_relationship_read_tools(registry, context)
    register_relationship_management_write_tools(registry, context)

    register_media_write_tools(registry, context)

    return registry


def list_registered_tool_names_for_policy_audit() -> list[str]:
    """Return all tool names declared by the tool registry builder.

    This helper intentionally uses placeholder dependencies because only
    registration-time metadata is needed (tool names/schemas), not execution.
    """
    sentinel = object()
    registry = create_tool_registry(
        account_usecases=sentinel,
        postjob_usecases=sentinel,
        hashtag_use_cases=sentinel,
        collection_use_cases=sentinel,
        media_use_cases=sentinel,
        story_use_cases=sentinel,
        highlight_use_cases=sentinel,
        comment_use_cases=sentinel,
        direct_use_cases=sentinel,
        insight_use_cases=sentinel,
        relationship_use_cases=sentinel,
        account_profile_usecases=sentinel,
        account_auth_usecases=sentinel,
        account_proxy_usecases=sentinel,
        account_edit_usecases=sentinel,
        proxy_pool_usecases=sentinel,
    )
    return registry.get_registered_tool_names()
