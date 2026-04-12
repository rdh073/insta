"""Goal parsing and goal-related reasoning helpers for smart engagement."""

from __future__ import annotations

from typing import Any


def _parse_goal(goal: str) -> dict:
    """Parse operator goal string into structured form.

    Examples:
        "comment on educational posts" → {intent: comment, action_type: comment, target_type: post}
        "follow accounts in tech space" → {intent: follow, action_type: follow, target_type: account}
        "like recent posts" → {intent: like, action_type: like, target_type: post}
    """
    goal_lower = goal.lower()

    # Derive action_type from goal keywords
    if "comment" in goal_lower:
        action_type = "comment"
        target_type = "post"
    elif "dm" in goal_lower or "direct message" in goal_lower or "message" in goal_lower:
        action_type = "dm"
        target_type = "account"
    elif "like" in goal_lower:
        action_type = "like"
        target_type = "post"
    elif "follow" in goal_lower:
        action_type = "follow"
        target_type = "account"
    else:
        # Default: follow account
        action_type = "follow"
        target_type = "account"

    # Extract content constraints from goal
    constraints: dict[str, Any] = {}
    if "educational" in goal_lower:
        constraints["content_filter"] = "educational"
    elif "tech" in goal_lower or "technology" in goal_lower:
        constraints["niche"] = "technology"
    elif "fitness" in goal_lower or "health" in goal_lower:
        constraints["niche"] = "health/fitness"

    return {
        "intent": goal,
        "action_type": action_type,
        "target_type": target_type,
        "constraints": constraints,
    }


def _expected_outcome(action_type: str) -> str:
    """Return expected outcome string for action type."""
    outcomes = {
        "follow": "Account followed; may receive follow-back",
        "dm": "Direct message sent; awaiting reply",
        "comment": "Comment posted; increases visibility",
        "like": "Post liked; increases account visibility",
        "skip": "Action skipped; no engagement taken",
    }
    return outcomes.get(action_type, "Unknown outcome")


def _account_not_healthy_reason(health: dict) -> str:
    """Return human-readable reason why account is not healthy."""
    if health.get("login_state") != "logged_in":
        return "Account session not loaded — please log in again from the Accounts page"
    if health.get("cooldown_until") is not None:
        return f"Account in cooldown until {health.get('cooldown_until')}"
    if health.get("status") != "active":
        return f"Account status: {health.get('status')} — account is not active"
    return "Account not ready"
