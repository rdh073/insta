"""Capabilities routes for Instagram transport."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/capabilities")
def get_instagram_capabilities():
    """Expose vertical ownership contract for Instagram transport."""
    return {
        "owner": "application_usecases",
        "verticals": [
            "media",
            "story",
            "comment",
            "direct",
            "hashtag",
            "highlight",
            "collection",
            "insight",
        ],
        "phase": 9,
    }
