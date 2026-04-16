"""Tool policy classification for operator copilot.

This module owns the tool allowlist, classification, and policy rules.
It is the single source of truth for: tool risk level, approval requirements,
and explicitly-documented policy-only exceptions.

Invariants enforced here:
- Tools NOT in the allowlist are BLOCKED by default (deny-unknown).
- BLOCKED tools can never be routed to execution regardless of approval.
- WRITE_SENSITIVE tools require approval_result == "approved" before execution.
- READ_ONLY tools do not require approval.
- Policy parity validation lives here, NOT in prompts, adapters, or the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ToolPolicy(str, Enum):
    """Risk classification for a tool."""

    READ_ONLY = "read_only"
    """Safe to execute without operator approval.

    Examples: get_followers, get_posts, search_hashtags.
    """

    WRITE_SENSITIVE = "write_sensitive"
    """Modifies external state; requires explicit operator approval.

    Examples: follow_user, send_direct_message, publish_post.
    """

    BLOCKED = "blocked"
    """Never execute regardless of LLM request or operator approval.

    Reserved for irreversible / ToS-violating / mass-action tools.
    Examples: delete_account, bulk_dm, scrape_users.
    """


@dataclass(frozen=True)
class ToolClassification:
    """Immutable classification for a single tool."""

    policy: ToolPolicy
    """Risk policy for this tool."""

    requires_approval: bool
    """True iff operator must approve before execution.

    Always False for BLOCKED (they are never executed).
    """

    reason: str
    """Human-readable rationale for this classification.

    Included in audit log and approval payload so the operator understands
    why a tool was flagged.
    """


# ── Default classification for unknown tools ──────────────────────────────────
_UNKNOWN_TOOL_BLOCK = ToolClassification(
    policy=ToolPolicy.BLOCKED,
    requires_approval=False,
    reason="unknown tool — not in allowlist",
)

# Explicit policy-only entries that are intentionally not in the runtime tool
# registry. These are retained for compatibility with historical traces/tests
# and for defensive deny-lists of unsafe legacy names.
_INTENTIONAL_POLICY_ONLY_EXCEPTIONS: dict[str, str] = {
    # Defensive blocked names: must stay classified as BLOCKED even when absent
    # from the runtime registry.
    "delete_account": "legacy blocked action retained as explicit deny-list entry",
    "mass_unfollow": "legacy blocked mass-action retained as explicit deny-list entry",
    "bulk_dm": "legacy blocked spam action retained as explicit deny-list entry",
    "scrape_users": "legacy blocked scraping action retained as explicit deny-list entry",
    # Legacy aliases used by older prompts/tests before the tool-registry split.
    "get_user_profile": "legacy read alias retained for compatibility",
    "get_followers": "legacy read alias retained for compatibility",
    "get_following": "legacy read alias retained for compatibility",
    "get_posts": "legacy read alias retained for compatibility",
    "get_post_details": "legacy read alias retained for compatibility",
    "get_scheduled_posts": "legacy read alias retained for compatibility",
    "get_engagement_stats": "legacy read alias retained for compatibility",
    "publish_post": "legacy write alias retained for compatibility",
    "delete_post": "legacy write alias retained for compatibility",
    "update_profile": "legacy write alias retained for compatibility",
}


class ToolPolicyRegistry:
    """Allowlist-based tool classification registry.

    Usage::

        registry = ToolPolicyRegistry()
        cls = registry.classify("get_followers")
        # ToolClassification(policy=READ_ONLY, requires_approval=False, ...)

        flags = registry.classify_calls([{"id": "c1", "name": "follow_user", ...}])
        # {"c1": "write_sensitive"}

    Design notes:
    - Unknown tools default to BLOCKED (deny-unknown principle).
    - The registry is immutable once instantiated; update _CLASSIFICATIONS to
      add new tools rather than patching at runtime.
    - Tool names must match exactly what ToolExecutorPort receives.
    """

    _CLASSIFICATIONS: dict[str, ToolClassification] = {
        # ── App operator tools (actual tool_registry/* tools) ─────────────────
        # These are the real tools available in the app's ToolRegistry.
        # Named after handlers registered in app/adapters/ai/tool_registry/*.
        "list_accounts": ToolClassification(
            ToolPolicy.READ_ONLY, False, "lists all managed accounts and their status"
        ),
        "list_proxy_pool": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads the current proxy pool and its health status"
        ),
        "pick_proxy": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads one working proxy candidate from the pool"
        ),
        "get_post_jobs": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads recent post jobs and their status"
        ),
        "relogin_account": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "re-authenticates an account (modifies session state)"
        ),
        "logout_account": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "removes an account from the system"
        ),
        "set_account_proxy": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "modifies account proxy configuration"
        ),
        "set_account_privacy": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE,
            True,
            "toggles account privacy (public ↔ private), changes audience for all posts",
        ),
        "edit_account_profile": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE,
            True,
            "edits the authenticated account's profile fields (name, biography, external URL)",
        ),
        "set_account_presence": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE,
            True,
            "toggles the 'show activity status' presence flag for the account",
        ),
        "import_proxies": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "imports proxy records into the proxy pool"
        ),
        "recheck_proxy_pool": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "re-tests the proxy pool and can remove dead entries"
        ),
        "delete_proxy": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "removes a proxy from the pool"
        ),
        "check_proxy": ToolClassification(
            ToolPolicy.READ_ONLY, False, "tests proxy reachability — no state mutation"
        ),
        # ── Read-only: account & profile ─────────────────────────────────────
        "get_account_info": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads account metadata"
        ),
        # Legacy aliases kept for backward compatibility with tests and older prompts.
        "get_user_profile": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads a user's public profile"
        ),
        "get_followers": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads follower list (legacy alias)"
        ),
        "get_following": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads following list (legacy alias)"
        ),
        "list_followers": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads follower list"
        ),
        "list_following": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads following list"
        ),
        "search_followers": ToolClassification(
            ToolPolicy.READ_ONLY, False, "searches within a follower list (server-side)"
        ),
        "search_following": ToolClassification(
            ToolPolicy.READ_ONLY, False, "searches within a following list (server-side)"
        ),
        # ── Read-only: content & discovery ───────────────────────────────────
        "get_posts": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads post list for an account"
        ),
        "get_post_details": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads a single post's metadata"
        ),
        "get_hashtag_posts": ToolClassification(
            ToolPolicy.READ_ONLY, False, "searches posts by hashtag"
        ),
        "get_collection_posts": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads saved collection posts"
        ),
        "get_scheduled_posts": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads the scheduled post queue"
        ),
        "get_engagement_stats": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads engagement metrics for an account"
        ),
        # ── Read-only: media ──────────────────────────────────────────────────
        "get_media_by_pk": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads a single post by numeric ID"
        ),
        "get_media_by_code": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads a single post by shortcode"
        ),
        "get_user_medias": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads post list for a user"
        ),
        "get_media_oembed": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads oEmbed metadata for a public media URL"
        ),
        # ── Read-only: discovery ──────────────────────────────────────────────
        "search_hashtags": ToolClassification(
            ToolPolicy.READ_ONLY, False, "searches hashtag metadata by query"
        ),
        "get_hashtag": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads metadata for one hashtag"
        ),
        "list_collections": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads saved collection metadata for the account"
        ),
        # ── Read-only: stories & highlights ──────────────────────────────────
        "get_story": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads one story with overlay counts"
        ),
        "list_user_stories": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads active stories for a user"
        ),
        "get_highlight": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads one highlight and its story items"
        ),
        "list_user_highlights": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads highlight reels for a user"
        ),
        # ── Read-only: comments ───────────────────────────────────────────────
        "list_comments": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads comments on a post"
        ),
        # ── Read-only: direct messages ────────────────────────────────────────
        "list_inbox_threads": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads DM inbox threads"
        ),
        "list_pending_threads": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads pending DM requests"
        ),
        "search_threads": ToolClassification(
            ToolPolicy.READ_ONLY, False, "searches DM threads"
        ),
        "get_direct_thread": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads one DM thread and its messages"
        ),
        "list_direct_messages": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads messages inside a DM thread"
        ),
        # ── Read-only: analytics ──────────────────────────────────────────────
        "get_media_insight": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads analytics for a single post"
        ),
        "list_media_insights": ToolClassification(
            ToolPolicy.READ_ONLY, False, "reads analytics for multiple posts"
        ),
        # ── Write-sensitive: social actions ──────────────────────────────────
        "follow_user": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "modifies follow relationship"
        ),
        "unfollow_user": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "modifies follow relationship"
        ),
        "remove_follower": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "removes a follower from account"
        ),
        "close_friend_add": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "modifies Close Friends list (story audience)"
        ),
        "close_friend_remove": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "modifies Close Friends list (story audience)"
        ),
        "like_post": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "creates a public like action"
        ),
        "unlike_post": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "removes a public like action"
        ),
        "create_comment": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "creates a public comment on a post"
        ),
        "delete_comment": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "deletes a public comment"
        ),
        "like_comment": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "likes a public comment"
        ),
        "unlike_comment": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "removes like from a public comment"
        ),
        "pin_comment": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "pins a public comment on owned media"
        ),
        "unpin_comment": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "unpins a public comment on owned media"
        ),
        "send_direct_message": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "sends a direct message to a user"
        ),
        "send_message_to_thread": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "sends a direct message into an existing thread"
        ),
        "find_or_create_direct_thread": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "creates or reuses a DM thread for specific participants"
        ),
        "delete_direct_message": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "deletes a direct message from a thread"
        ),
        "approve_pending_direct_thread": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "approves a pending direct-message request thread"
        ),
        "mark_direct_thread_seen": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "marks a direct-message thread as seen"
        ),
        # ── Write-sensitive: stories ──────────────────────────────────────────
        "delete_story": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "deletes a story"
        ),
        "mark_stories_seen": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "marks stories as seen/skipped"
        ),
        # ── Write-sensitive: highlights ───────────────────────────────────────
        "create_highlight": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "creates a new story highlight reel"
        ),
        "delete_highlight": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "permanently deletes a story highlight"
        ),
        "change_highlight_title": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "renames a story highlight"
        ),
        "add_stories_to_highlight": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "adds stories to a story highlight"
        ),
        "remove_stories_from_highlight": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "removes stories from a story highlight"
        ),
        # ── Write-sensitive: content management ──────────────────────────────
        "schedule_post": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "queues content for scheduled publishing"
        ),
        "publish_post": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "publishes content immediately"
        ),
        "delete_post": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "permanently deletes a post"
        ),
        "update_profile": ToolClassification(
            ToolPolicy.WRITE_SENSITIVE, True, "modifies account profile fields"
        ),
        # ── Blocked: irreversible / ToS-violating ─────────────────────────────
        "delete_account": ToolClassification(
            ToolPolicy.BLOCKED, False, "irreversible account deletion"
        ),
        "mass_unfollow": ToolClassification(
            ToolPolicy.BLOCKED, False, "mass action violates engagement policies"
        ),
        "bulk_dm": ToolClassification(
            ToolPolicy.BLOCKED, False, "mass DM violates anti-spam policies"
        ),
        "scrape_users": ToolClassification(
            ToolPolicy.BLOCKED, False, "bulk scraping violates platform ToS"
        ),
    }

    def classify(self, tool_name: str) -> ToolClassification:
        """Return classification for a tool name.

        Unknown tools return BLOCKED with reason "not in allowlist".
        """
        return self._CLASSIFICATIONS.get(tool_name, _UNKNOWN_TOOL_BLOCK)

    @classmethod
    def classified_tool_names(cls) -> set[str]:
        """Return all explicit tool names known to policy."""
        return set(cls._CLASSIFICATIONS.keys())

    @classmethod
    def intentional_policy_only_exceptions(cls) -> dict[str, str]:
        """Return documented policy-only names that may stay non-registered."""
        return dict(_INTENTIONAL_POLICY_ONLY_EXCEPTIONS)

    @classmethod
    def build_parity_report(cls, registered_tool_names: Iterable[str]) -> dict[str, object]:
        """Build machine-readable policy/registry parity report.

        Args:
            registered_tool_names: Actual runtime names registered by the tool
                registry builder.

        Returns:
            Dict with coverage details:
            - registered_only: tools registered but missing in policy (CI fail)
            - policy_only: tools in policy but absent from registry
            - intentional_exceptions: policy_only entries explicitly documented
            - policy_only_unexpected: policy_only entries not in exceptions (CI fail)
            - stale_intentional_exceptions: exception names no longer policy_only
            - is_parity_ok: overall parity status for CI
        """
        registered = {name for name in registered_tool_names if name}
        policy = cls.classified_tool_names()
        policy_only = policy - registered
        registered_only = registered - policy

        declared_exceptions = set(_INTENTIONAL_POLICY_ONLY_EXCEPTIONS.keys())
        intentional_exceptions = policy_only & declared_exceptions
        policy_only_unexpected = policy_only - declared_exceptions
        stale_intentional_exceptions = declared_exceptions - policy_only

        return {
            "registered_only": sorted(registered_only),
            "policy_only": sorted(policy_only),
            "intentional_exceptions": sorted(intentional_exceptions),
            "policy_only_unexpected": sorted(policy_only_unexpected),
            "stale_intentional_exceptions": sorted(stale_intentional_exceptions),
            "intentional_exception_reasons": {
                name: _INTENTIONAL_POLICY_ONLY_EXCEPTIONS[name]
                for name in sorted(intentional_exceptions)
            },
            "is_parity_ok": not registered_only
            and not policy_only_unexpected
            and not stale_intentional_exceptions,
        }

    def classify_calls(
        self, proposed_tool_calls: list[dict]
    ) -> dict[str, str]:
        """Classify a list of proposed tool calls.

        Args:
            proposed_tool_calls: List of dicts with at least {"id": ..., "name": ...}

        Returns:
            Dict mapping call_id → policy string ("read_only", "write_sensitive", "blocked")
        """
        return {
            call["id"]: self.classify(call["name"]).policy.value
            for call in proposed_tool_calls
        }

    def has_blocked(self, proposed_tool_calls: list[dict]) -> bool:
        """True if any proposed call targets a BLOCKED tool."""
        return any(
            self.classify(call["name"]).policy == ToolPolicy.BLOCKED
            for call in proposed_tool_calls
        )

    def has_write_sensitive(self, proposed_tool_calls: list[dict]) -> bool:
        """True if any proposed call targets a WRITE_SENSITIVE tool."""
        return any(
            self.classify(call["name"]).policy == ToolPolicy.WRITE_SENSITIVE
            for call in proposed_tool_calls
        )

    def all_read_only(self, proposed_tool_calls: list[dict]) -> bool:
        """True if every proposed call targets a READ_ONLY tool."""
        return all(
            self.classify(call["name"]).policy == ToolPolicy.READ_ONLY
            for call in proposed_tool_calls
        )

    def filter_executable(
        self, proposed_tool_calls: list[dict]
    ) -> list[dict]:
        """Return only the calls that are not BLOCKED.

        Used when the planner mixes blocked and non-blocked calls; the blocked
        ones are stripped and the rest can proceed through the policy gate.
        """
        return [
            call
            for call in proposed_tool_calls
            if self.classify(call["name"]).policy != ToolPolicy.BLOCKED
        ]
