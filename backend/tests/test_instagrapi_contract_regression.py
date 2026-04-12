"""Focused regression locks for instagrapi 2.3.0 adapter assumptions."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock

import pytest

from app.adapters.instagram.comment_reader import InstagramCommentReaderAdapter
from app.adapters.instagram.direct_reader import InstagramDirectReaderAdapter
from app.adapters.instagram.direct_writer import InstagramDirectWriterAdapter
from app.adapters.instagram.insight_reader import InstagramInsightReaderAdapter
from app.adapters.instagram.track_catalog import InstagramTrackCatalogAdapter
from app.application.dto.instagram_analytics_dto import MediaInsightSummary, TrackSummary
from app.application.dto.instagram_comment_dto import CommentPage
from app.application.dto.instagram_direct_dto import (
    DirectSearchUserSummary,
    DirectThreadSummary,
)


def _repo_with(client: Any) -> Mock:
    repo = Mock()
    repo.get.return_value = client
    return repo


def _make_vendor_comment(pk: int, text: str) -> Mock:
    comment = Mock()
    comment.pk = pk
    comment.text = text
    comment.user = Mock()
    comment.user.pk = 10_000 + pk
    comment.user.username = f"user-{pk}"
    comment.user.full_name = f"User {pk}"
    comment.user.profile_pic_url = f"https://example.com/u/{pk}.jpg"
    comment.created_at_utc = datetime(2024, 1, 1, tzinfo=timezone.utc)
    comment.content_type = "comment"
    comment.status = "Active"
    comment.has_liked = False
    comment.like_count = 0
    return comment


def _runtime_instagrapi_contract_snapshot() -> dict[str, Any] | None:
    script = """
import importlib.metadata
import inspect
import json

try:
    from instagrapi import Client
except Exception as exc:
    print(json.dumps({"available": False, "error": f"{type(exc).__name__}: {exc}"}))
    raise SystemExit(0)


def _method_snapshot(name: str):
    fn = getattr(Client, name, None)
    if fn is None:
        return None
    sig = inspect.signature(fn)
    snapshot = {
        "params": list(sig.parameters.keys()),
        "return": repr(sig.return_annotation),
    }
    try:
        source = inspect.getsource(fn)
    except Exception:
        source = ""
    snapshot["source_mentions_usershort"] = "UserShort" in source
    snapshot["source_mentions_edges"] = 'stats["edges"]' in source or "stats['edges']" in source
    return snapshot


version = None
try:
    version = importlib.metadata.version("instagrapi")
except Exception:
    pass

payload = {"available": True, "version": version}
for method in (
    "search_music",
    "direct_search",
    "direct_thread_by_participants",
    "media_comments_chunk",
    "insights_media_feed_all",
):
    payload[method] = _method_snapshot(method)

print(json.dumps(payload))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return None
    if not payload.get("available"):
        return None
    return payload


def test_runtime_signatures_match_locked_instagrapi_230_contract_when_available():
    """Lock external contract shape for installed instagrapi runtime."""
    snapshot = _runtime_instagrapi_contract_snapshot()
    if snapshot is None:
        pytest.skip("instagrapi is not installed in the runtime interpreter")

    if snapshot.get("version") is not None:
        assert snapshot["version"] == "2.3.0"

    search_music = snapshot["search_music"]
    assert search_music["params"] == ["self", "query"]
    assert "limit" not in search_music["params"]

    direct_search = snapshot["direct_search"]
    assert direct_search["params"][:2] == ["self", "query"]
    assert "UserShort" in direct_search["return"] or direct_search["source_mentions_usershort"]

    direct_thread = snapshot["direct_thread_by_participants"]
    assert direct_thread["params"] == ["self", "user_ids"]
    assert "Dict" in direct_thread["return"] or "dict" in direct_thread["return"].lower()

    comments_chunk = snapshot["media_comments_chunk"]
    assert comments_chunk["params"] == ["self", "media_id", "max_amount", "min_id"]
    assert "Tuple" in comments_chunk["return"] and "str" in comments_chunk["return"]

    insights_feed = snapshot["insights_media_feed_all"]
    assert insights_feed["params"][:5] == [
        "self",
        "post_type",
        "time_frame",
        "data_ordering",
        "count",
    ]
    assert insights_feed["source_mentions_edges"] is True


def test_search_music_contract_query_only_signature_no_limit_forwarding():
    """Contract: adapter must not pass limit kwarg to search_music(query-only)."""

    class _StrictTrackClient:
        def __init__(self):
            self.queries: list[str] = []

        def search_music(self, query: str):
            self.queries.append(query)
            track = Mock()
            track.canonical_id = 123
            track.title = "Contract Song"
            track.name = "Contract Song"
            track.artist_name = "Contract Artist"
            track.duration_in_ms = 120_000
            return [track]

    client = _StrictTrackClient()
    adapter = InstagramTrackCatalogAdapter(_repo_with(client))

    results = adapter.search_tracks("acc-1", "contract-query", limit=1)

    assert client.queries == ["contract-query"]
    assert len(results) == 1
    assert isinstance(results[0], TrackSummary)
    assert results[0].canonical_id == "123"


def test_direct_search_contract_returns_usershort_shaped_results():
    """Contract: direct_search result items are mapped as UserShort-like users."""

    class _UserShortLike:
        def __init__(
            self,
            pk: int,
            username: str,
            full_name: str,
            profile_pic_url: str,
            is_private: bool,
            is_verified: bool,
        ):
            self.pk = pk
            self.username = username
            self.full_name = full_name
            self.profile_pic_url = profile_pic_url
            self.is_private = is_private
            self.is_verified = is_verified

    class _StrictDirectSearchClient:
        def direct_search(self, query: str, mode: str = "universal"):
            assert query == "alice"
            assert mode == "universal"
            return [
                _UserShortLike(
                    pk=77,
                    username="alice",
                    full_name="Alice",
                    profile_pic_url="https://example.com/alice.jpg",
                    is_private=False,
                    is_verified=True,
                )
            ]

    adapter = InstagramDirectReaderAdapter(_repo_with(_StrictDirectSearchClient()))
    results = adapter.search_threads("acc-1", "alice")

    assert len(results) == 1
    assert isinstance(results[0], DirectSearchUserSummary)
    assert results[0].user_id == 77
    assert results[0].username == "alice"
    assert not hasattr(results[0], "direct_thread_id")


def test_direct_thread_by_participants_contract_accepts_dict_payload():
    """Contract: direct_thread_by_participants response is a dict payload."""

    class _StrictThreadClient:
        def direct_thread_by_participants(self, user_ids: list[int]):
            assert user_ids == [100, 101]
            return {
                "status": "ok",
                "thread": {
                    "thread_id": "340282366841710300949128171234567890123",
                    "pk": "178612312342",
                    "users": [
                        {
                            "pk": "100",
                            "username": "alice",
                            "full_name": "Alice A",
                            "profile_pic_url": "https://example.com/alice.jpg",
                            "is_private": False,
                        },
                        {
                            "pk": 101,
                            "username": "bob",
                            "full_name": "Bob B",
                            "is_private": True,
                        },
                    ],
                    "items": [
                        {
                            "item_id": "30076214123123123123123864",
                            "user_id": "100",
                            "timestamp": "1700000000000000",
                            "item_type": "text",
                            "text": "hello",
                        }
                    ],
                },
            }

    adapter = InstagramDirectWriterAdapter(_repo_with(_StrictThreadClient()))
    result = adapter.find_or_create_thread("acc-1", [100, 101])

    assert isinstance(result, DirectThreadSummary)
    assert result.direct_thread_id == "340282366841710300949128171234567890123"
    assert result.pk == 178612312342
    assert [participant.user_id for participant in result.participants] == [100, 101]
    assert result.last_message is not None
    assert result.last_message.direct_message_id == "30076214123123123123123864"


def test_media_comments_chunk_contract_treats_cursor_as_opaque_string():
    """Contract: media_comments_chunk min_id/next_min_id stays an opaque string token."""

    class _StrictCommentClient:
        def __init__(self):
            self.seen_min_id: list[str | None] = []

        def media_comments_chunk(
            self, media_id: str, max_amount: int, min_id: str = None
        ):
            assert media_id == "media-1"
            assert max_amount == 10
            self.seen_min_id.append(min_id)
            return (
                [_make_vendor_comment(pk=1, text="hello")],
                "NEXT::opaque=/cursor==",
            )

    client = _StrictCommentClient()
    adapter = InstagramCommentReaderAdapter(_repo_with(client))
    result = adapter.list_comments_page(
        "acc-1",
        "media-1",
        page_size=10,
        cursor="INPUT::opaque=/cursor==",
    )

    assert isinstance(result, CommentPage)
    assert client.seen_min_id == ["INPUT::opaque=/cursor=="]
    assert result.next_cursor == "NEXT::opaque=/cursor=="


def test_insights_media_feed_all_contract_edge_node_payload_mapping():
    """Contract: list_media_insights accepts edge/node payload from feed_all."""

    class _StrictInsightsClient:
        def __init__(self):
            self.calls: list[dict[str, Any]] = []

        def insights_media_feed_all(
            self,
            post_type: str = "ALL",
            time_frame: str = "TWO_YEARS",
            data_ordering: str = "REACH_COUNT",
            count: int = 0,
        ):
            self.calls.append(
                {
                    "post_type": post_type,
                    "time_frame": time_frame,
                    "data_ordering": data_ordering,
                    "count": count,
                }
            )
            return {
                "data": {
                    "shadow_instagram_user": {
                        "business_manager": {
                            "top_posts_unit": {
                                "top_posts": {
                                    "edges": [
                                        {
                                            "node": {
                                                "id": "123_7",
                                                "reach_count": 321,
                                                "impression_count": 654,
                                                "like_count": 11,
                                                "comment_count": 2,
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            }

    client = _StrictInsightsClient()
    adapter = InstagramInsightReaderAdapter(_repo_with(client))
    results = adapter.list_media_insights("acc-1")

    assert client.calls == [
        {
            "post_type": "ALL",
            "time_frame": "TWO_YEARS",
            "data_ordering": "REACH_COUNT",
            "count": 0,
        }
    ]
    assert len(results) == 1
    assert isinstance(results[0], MediaInsightSummary)
    assert results[0].media_pk == 123
    assert results[0].reach_count == 321
    assert results[0].impression_count == 654
