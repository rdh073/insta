"""Candidate scoring and risk threshold helpers for smart engagement."""

from __future__ import annotations

import math

# Risk threshold: "high" stops workflow without approval.
HIGH_RISK_THRESHOLD = "high"


def _score_candidate(candidate: dict, structured_goal: dict) -> float:
    """Score a candidate by goal relevance and engagement quality."""
    metadata = candidate.get("metadata", {})
    score = 0.0

    # Engagement rate is primary signal
    engagement_rate = metadata.get("engagement_rate", 0.0)
    score += engagement_rate * 100

    # Follower count (log scale - prefer mid-size accounts)
    followers = metadata.get("follower_count", 0)
    if followers > 0:
        score += min(math.log10(followers), 5)  # cap at 5 points

    # Recent activity bonus
    recent_posts = metadata.get("recent_posts", 0)
    score += min(recent_posts * 0.5, 3)  # cap at 3 points

    return score
