"""Tests for InstagramDataAdapter use-case-only integration."""

from __future__ import annotations

import asyncio
import sys
import types
from datetime import datetime, timezone

# Minimal shim so importing ai_copilot state does not require langgraph package.
if "langgraph.graph" not in sys.modules:
    langgraph_module = types.ModuleType("langgraph")
    graph_module = types.ModuleType("langgraph.graph")
    graph_module.add_messages = lambda x: x
    langgraph_module.graph = graph_module
    sys.modules["langgraph"] = langgraph_module
    sys.modules["langgraph.graph"] = graph_module

from ai_copilot.adapters.instagram_data_adapter import InstagramDataAdapter
from app.application.dto.instagram_identity_dto import (
    AuthenticatedAccountProfile,
    PublicUserProfile,
)
from app.application.dto.instagram_media_dto import MediaSummary


class _StubIdentityUseCases:
    def __init__(self):
        self.me_calls: list[str] = []
        self.by_id_calls: list[tuple[str, int]] = []
        self.by_username_calls: list[tuple[str, str]] = []

    def get_authenticated_account(self, account_id: str) -> AuthenticatedAccountProfile:
        self.me_calls.append(account_id)
        return AuthenticatedAccountProfile(pk=999, username="operator")

    def get_public_user_by_id(self, account_id: str, user_id: int) -> PublicUserProfile:
        self.by_id_calls.append((account_id, user_id))
        return PublicUserProfile(pk=user_id, username=f"user{user_id}", follower_count=12)

    def get_public_user_by_username(self, account_id: str, username: str) -> PublicUserProfile:
        self.by_username_calls.append((account_id, username))
        return PublicUserProfile(pk=333, username=username, follower_count=44)


class _StubRelationshipUseCases:
    def __init__(self):
        self.follower_calls: list[tuple[str, str, int]] = []
        self.following_calls: list[tuple[str, str, int]] = []

    def list_followers(self, account_id: str, username: str, amount: int = 50) -> list[PublicUserProfile]:
        self.follower_calls.append((account_id, username, amount))
        return [
            PublicUserProfile(pk=1, username="alice", follower_count=500, media_count=10),
            PublicUserProfile(pk=2, username="bob", follower_count=5, media_count=0),
        ]

    def list_following(self, account_id: str, username: str, amount: int = 50) -> list[PublicUserProfile]:
        self.following_calls.append((account_id, username, amount))
        return [PublicUserProfile(pk=3, username="carol", follower_count=200, media_count=4)]


class _StubMediaUseCases:
    def __init__(self):
        self.calls: list[tuple[str, int, int]] = []

    def get_user_medias(self, account_id: str, user_id: int, amount: int = 12) -> list[MediaSummary]:
        self.calls.append((account_id, user_id, amount))
        return [
            MediaSummary(
                pk=101,
                media_id="101_1",
                code="CODE101",
                media_type=1,
                product_type="feed",
                owner_username="author_a",
                caption_text="Caption A",
                like_count=50,
                comment_count=10,
                taken_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
            MediaSummary(
                pk=102,
                media_id="102_1",
                code="CODE102",
                media_type=1,
                product_type="feed",
                owner_username="author_b",
                caption_text="Caption B",
                like_count=5,
                comment_count=1,
                taken_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
            ),
        ][:amount]


def test_get_recent_posts_uses_media_usecases_and_identity():
    identity = _StubIdentityUseCases()
    relationships = _StubRelationshipUseCases()
    media = _StubMediaUseCases()
    adapter = InstagramDataAdapter(
        identity_usecases=identity,
        relationship_usecases=relationships,
        media_usecases=media,
    )

    targets = asyncio.run(adapter.get_recent_posts(account_id="acc-1", limit=2))

    assert len(targets) == 2
    assert targets[0]["target_id"] == "101"
    assert targets[0]["metadata"]["owner"] == "author_a"
    assert identity.me_calls == ["acc-1"]
    assert media.calls == [("acc-1", 999, 2)]


def test_get_followers_uses_relationship_usecases():
    identity = _StubIdentityUseCases()
    relationships = _StubRelationshipUseCases()
    media = _StubMediaUseCases()
    adapter = InstagramDataAdapter(
        identity_usecases=identity,
        relationship_usecases=relationships,
        media_usecases=media,
    )

    targets = asyncio.run(adapter.get_followers(account_id="acc-1", limit=2))

    assert len(targets) == 2
    assert targets[0]["target_type"] == "account"
    assert relationships.follower_calls == [("acc-1", "operator", 2)]


def test_get_target_metadata_uses_identity_usecases():
    identity = _StubIdentityUseCases()
    relationships = _StubRelationshipUseCases()
    media = _StubMediaUseCases()
    adapter = InstagramDataAdapter(
        identity_usecases=identity,
        relationship_usecases=relationships,
        media_usecases=media,
    )

    metadata = asyncio.run(adapter.get_target_metadata(account_id="acc-1", target_id="someone"))

    assert metadata["username"] == "someone"
    assert identity.by_username_calls == [("acc-1", "someone")]
