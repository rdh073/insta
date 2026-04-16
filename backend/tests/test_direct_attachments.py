"""Tests for direct-message attachment and share capabilities.

Covers:
- Adapter layer (mocked instagrapi Client): correct vendor-call routing + translation.
- File-type allowlist rejects non-allowed extensions at the adapter boundary.
- Use-case validation: thread_ids > 32, missing file, oversize video.
- Router multipart + JSON handling.
- Policy classification for the five new tools.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest


# Defensive langgraph shim: other tests in the suite stub ``langgraph`` as a
# plain module which breaks ``app.adapters.http.dependencies -> bootstrap ->
# checkpoint_factory_adapter`` when it imports langgraph.checkpoint.memory.
# Install the minimal surface our router test needs before touching bootstrap.
def _ensure_pkg(name: str) -> types.ModuleType:
    mod = sys.modules.get(name) or types.ModuleType(name)
    if not hasattr(mod, "__path__"):
        mod.__path__ = []  # type: ignore[attr-defined]
    sys.modules[name] = mod
    return mod


def _install_langgraph_stubs() -> None:
    """Install minimal langgraph surface our router test's import chain needs."""
    langgraph_mod = _ensure_pkg("langgraph")

    checkpoint_mod = _ensure_pkg("langgraph.checkpoint")
    langgraph_mod.checkpoint = checkpoint_mod

    if "langgraph.checkpoint.memory" not in sys.modules:
        memory_mod = types.ModuleType("langgraph.checkpoint.memory")

        class MemorySaver:
            pass

        memory_mod.MemorySaver = MemorySaver
        checkpoint_mod.memory = memory_mod
        sys.modules["langgraph.checkpoint.memory"] = memory_mod

    graph_mod = sys.modules.get("langgraph.graph")
    if graph_mod is None:
        graph_mod = types.ModuleType("langgraph.graph")
        sys.modules["langgraph.graph"] = graph_mod
        langgraph_mod.graph = graph_mod
    for attr in ("END", "START"):
        if not hasattr(graph_mod, attr):
            setattr(graph_mod, attr, object())
    if not hasattr(graph_mod, "StateGraph"):
        class StateGraph:
            def __init__(self, *_a, **_k):
                pass

            def add_node(self, *_a, **_k):
                return self

            def add_edge(self, *_a, **_k):
                return self

            def add_conditional_edges(self, *_a, **_k):
                return self

            def set_entry_point(self, *_a, **_k):
                return self

            def compile(self, *_a, **_k):
                return self

        graph_mod.StateGraph = StateGraph
    if not hasattr(graph_mod, "add_messages"):
        graph_mod.add_messages = lambda a, b: list(a or []) + list(b or [])

    types_mod = sys.modules.get("langgraph.types")
    if types_mod is None:
        types_mod = types.ModuleType("langgraph.types")
        sys.modules["langgraph.types"] = types_mod
        langgraph_mod.types = types_mod
    if not hasattr(types_mod, "Command"):
        class Command:
            def __init__(self, *a, **k):
                pass

        types_mod.Command = Command
    if not hasattr(types_mod, "interrupt"):
        types_mod.interrupt = lambda *a, **k: None

    store_mod = _ensure_pkg("langgraph.store")
    langgraph_mod.store = store_mod
    if "langgraph.store.memory" not in sys.modules:
        store_memory_mod = types.ModuleType("langgraph.store.memory")

        class InMemoryStore:
            pass

        store_memory_mod.InMemoryStore = InMemoryStore
        store_mod.memory = store_memory_mod
        sys.modules["langgraph.store.memory"] = store_memory_mod


_install_langgraph_stubs()

from app.application.dto.instagram_direct_dto import DirectMessageAck
from app.application.use_cases.direct import DirectUseCases
from app.adapters.instagram.direct_writer import InstagramDirectWriterAdapter


# ---------------------------------------------------------------------------
# Adapter unit tests (mocked client, each vendor call exactly once)
# ---------------------------------------------------------------------------


def _make_adapter_with_mock_client():
    client = MagicMock()
    # Default responses with vendor-like objects carrying an ``id``.
    for attr in (
        "direct_send_photo",
        "direct_send_video",
        "direct_send_voice",
        "direct_media_share",
        "direct_story_share",
    ):
        getattr(client, attr).return_value = MagicMock(id="vendor-msg-1")

    repo = Mock()
    repo.get.return_value = client
    return InstagramDirectWriterAdapter(repo), client


def _write_tmp_file(tmp_path: Path, name: str, data: bytes = b"\x00") -> str:
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


class TestAdapterAttachmentMethods:
    def test_send_photo_routes_to_vendor(self, tmp_path):
        adapter, client = _make_adapter_with_mock_client()
        path = _write_tmp_file(tmp_path, "pic.jpg")

        ack = adapter.send_photo("acc-1", ["111"], path)

        client.direct_send_photo.assert_called_once_with(path=path, thread_ids=[111])
        assert isinstance(ack, DirectMessageAck)
        assert ack.kind == "photo"
        assert ack.thread_ids == ["111"]
        assert ack.message_id == "vendor-msg-1"

    def test_send_video_routes_to_vendor(self, tmp_path):
        adapter, client = _make_adapter_with_mock_client()
        path = _write_tmp_file(tmp_path, "clip.mp4")

        ack = adapter.send_video("acc-1", ["111", "222"], path)

        client.direct_send_video.assert_called_once_with(
            path=path, thread_ids=[111, 222]
        )
        assert ack.kind == "video"
        assert ack.thread_ids == ["111", "222"]

    def test_send_voice_routes_to_vendor(self, tmp_path):
        adapter, client = _make_adapter_with_mock_client()
        path = _write_tmp_file(tmp_path, "voice.m4a")

        ack = adapter.send_voice("acc-1", ["111"], path)

        client.direct_send_voice.assert_called_once_with(path=path, thread_ids=[111])
        assert ack.kind == "voice"

    def test_share_media_routes_to_vendor(self):
        adapter, client = _make_adapter_with_mock_client()

        ack = adapter.share_media("acc-1", ["111"], "1234_5678")

        client.direct_media_share.assert_called_once_with(
            media_id="1234_5678", thread_ids=[111]
        )
        assert ack.kind == "media_share"

    def test_share_story_routes_to_vendor(self):
        adapter, client = _make_adapter_with_mock_client()

        ack = adapter.share_story("acc-1", ["111"], 999)

        client.direct_story_share.assert_called_once_with(
            story_pk=999, thread_ids=[111]
        )
        assert ack.kind == "story_share"


class TestAdapterExceptionTranslation:
    """Vendor exceptions must be caught and translated to attached failures."""

    @pytest.mark.parametrize(
        "method_name,vendor_method,args",
        [
            ("send_photo", "direct_send_photo", ("photo.jpg",)),
            ("send_video", "direct_send_video", ("clip.mp4",)),
            ("send_voice", "direct_send_voice", ("voice.m4a",)),
        ],
    )
    def test_send_attachment_translates_vendor_exception(
        self, tmp_path, method_name, vendor_method, args
    ):
        adapter, client = _make_adapter_with_mock_client()
        getattr(client, vendor_method).side_effect = Exception("boom")
        file_path = _write_tmp_file(tmp_path, args[0])

        with pytest.raises(ValueError):
            getattr(adapter, method_name)("acc-1", ["111"], file_path)

    def test_share_media_translates_vendor_exception(self):
        adapter, client = _make_adapter_with_mock_client()
        client.direct_media_share.side_effect = Exception("rate limited")

        with pytest.raises(ValueError):
            adapter.share_media("acc-1", ["111"], "1234_5678")

    def test_share_story_translates_vendor_exception(self):
        adapter, client = _make_adapter_with_mock_client()
        client.direct_story_share.side_effect = Exception("story gone")

        with pytest.raises(ValueError):
            adapter.share_story("acc-1", ["111"], 42)


class TestAdapterFileTypeAllowlist:
    """The adapter rejects non-allowed extensions before any vendor call."""

    @pytest.mark.parametrize(
        "method_name,bad_name",
        [
            ("send_photo", "pic.gif"),
            ("send_video", "clip.mov"),
            ("send_voice", "audio.wav"),
        ],
    )
    def test_rejects_disallowed_extension(self, tmp_path, method_name, bad_name):
        adapter, client = _make_adapter_with_mock_client()
        path = _write_tmp_file(tmp_path, bad_name)

        with pytest.raises(ValueError, match="extension"):
            getattr(adapter, method_name)("acc-1", ["111"], path)

        # Ensure vendor never invoked.
        client.direct_send_photo.assert_not_called()
        client.direct_send_video.assert_not_called()
        client.direct_send_voice.assert_not_called()


# ---------------------------------------------------------------------------
# Use-case validation tests
# ---------------------------------------------------------------------------


def _build_use_cases(writer: Mock | None = None):
    account_repo = Mock()
    account_repo.get.return_value = {"username": "op"}
    client_repo = Mock()
    client_repo.exists.return_value = True

    if writer is None:
        writer = Mock()
    reader = Mock()
    identity = Mock()

    uc = DirectUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        direct_reader=reader,
        direct_writer=writer,
        identity_use_cases=identity,
    )
    return uc, writer


class TestUseCaseValidation:
    def test_send_photo_rejects_too_many_thread_ids(self, tmp_path):
        uc, writer = _build_use_cases()
        path = _write_tmp_file(tmp_path, "pic.jpg")
        thread_ids = [str(i) for i in range(33)]

        with pytest.raises(ValueError, match="at most 32"):
            uc.send_photo("acc-1", thread_ids, path)

        writer.send_photo.assert_not_called()

    def test_send_video_rejects_missing_file(self):
        uc, writer = _build_use_cases()
        with pytest.raises(ValueError, match="file not found"):
            uc.send_video("acc-1", ["111"], "/nonexistent/path.mp4")
        writer.send_video.assert_not_called()

    def test_send_voice_rejects_empty_thread_ids(self, tmp_path):
        uc, writer = _build_use_cases()
        path = _write_tmp_file(tmp_path, "voice.m4a")
        with pytest.raises(ValueError, match="non-empty"):
            uc.send_voice("acc-1", [], path)
        writer.send_voice.assert_not_called()

    def test_send_video_rejects_oversize(self, tmp_path, monkeypatch):
        uc, writer = _build_use_cases()
        path = _write_tmp_file(tmp_path, "big.mp4", b"\x00")

        original_getsize = os.path.getsize

        def fake_getsize(p):
            if p == path:
                return 101 * 1024 * 1024
            return original_getsize(p)

        monkeypatch.setattr(os.path, "getsize", fake_getsize)

        with pytest.raises(ValueError, match="exceeds maximum size"):
            uc.send_video("acc-1", ["111"], path)
        writer.send_video.assert_not_called()

    def test_share_media_rejects_empty_media_id(self):
        uc, writer = _build_use_cases()
        with pytest.raises(ValueError, match="media_id"):
            uc.share_media("acc-1", ["111"], "   ")
        writer.share_media.assert_not_called()

    def test_share_story_rejects_non_positive_pk(self):
        uc, writer = _build_use_cases()
        with pytest.raises(ValueError, match="story_pk"):
            uc.share_story("acc-1", ["111"], 0)
        writer.share_story.assert_not_called()


# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------


def _make_fake_direct_usecases():
    usecases = Mock()

    def _ack(kind):
        return DirectMessageAck(
            thread_ids=["111", "222"],
            kind=kind,
            message_id="mid-1",
            sent_at=None,
        )

    usecases.send_photo = Mock(return_value=_ack("photo"))
    usecases.send_video = Mock(return_value=_ack("video"))
    usecases.send_voice = Mock(return_value=_ack("voice"))
    usecases.share_media = Mock(return_value=_ack("media_share"))
    usecases.share_story = Mock(return_value=_ack("story_share"))
    return usecases


def _tiny_jpeg_bytes() -> bytes:
    # Minimal JPEG start-of-image + end-of-image markers. Contents irrelevant
    # because the router only persists the upload and hands the path to the
    # (mocked) use case.
    return b"\xff\xd8\xff\xd9"


def _make_router_test_app(fake_uc):
    """Build a tiny FastAPI app mounting only the direct-attachments router.

    Avoids pulling in ``app.main`` (and its AI/langgraph wiring) which makes
    the test robust against cross-test sys.modules pollution.
    """
    from fastapi import FastAPI
    from app.adapters.http.routers.direct import router as direct_router
    from app.adapters.http.dependencies import get_direct_usecases

    app = FastAPI()
    app.include_router(direct_router)
    app.dependency_overrides[get_direct_usecases] = lambda: fake_uc
    return app


class TestRouter:
    def test_send_photo_multipart_flow(self):
        from fastapi.testclient import TestClient

        fake_uc = _make_fake_direct_usecases()
        app = _make_router_test_app(fake_uc)
        with TestClient(app) as client:
            response = client.post(
                "/api/direct/acc-1/send/photo",
                files=[
                    ("file", ("sample.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")),
                    ("thread_ids", (None, "111")),
                    ("thread_ids", (None, "222")),
                ],
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["kind"] == "photo"
        assert body["threadIds"] == ["111", "222"]

        fake_uc.send_photo.assert_called_once()
        call_args = fake_uc.send_photo.call_args
        account_id, thread_ids, tmp_path = call_args[0]
        assert account_id == "acc-1"
        assert thread_ids == ["111", "222"]
        # Should be a temp filesystem path with .jpg suffix.
        assert tmp_path.endswith(".jpg")
        assert os.path.isfile(tmp_path)

    def test_share_media_json_flow(self):
        from fastapi.testclient import TestClient

        fake_uc = _make_fake_direct_usecases()
        app = _make_router_test_app(fake_uc)
        with TestClient(app) as client:
            response = client.post(
                "/api/direct/acc-1/share/media",
                json={"thread_ids": ["111", "222"], "media_id": "1234_5678"},
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["kind"] == "media_share"
        assert body["threadIds"] == ["111", "222"]

        fake_uc.share_media.assert_called_once_with("acc-1", ["111", "222"], "1234_5678")


# ---------------------------------------------------------------------------
# Policy classification test
# ---------------------------------------------------------------------------


class TestPolicyClassification:
    def test_new_tools_are_all_write_sensitive(self):
        from ai_copilot.application.operator_copilot_policy import (
            ToolPolicy,
            ToolPolicyRegistry,
        )

        registry = ToolPolicyRegistry()
        for name in (
            "dm_send_photo",
            "dm_send_video",
            "dm_send_voice",
            "dm_share_media",
            "dm_share_story",
        ):
            cls = registry.classify(name)
            assert cls.policy == ToolPolicy.WRITE_SENSITIVE, name
            assert cls.requires_approval is True, name

    def test_new_tools_registered_in_tool_registry(self):
        from app.adapters.ai.tool_registry.builder import (
            list_registered_tool_names_for_policy_audit,
        )

        names = set(list_registered_tool_names_for_policy_audit())
        for expected in (
            "dm_send_photo",
            "dm_send_video",
            "dm_send_voice",
            "dm_share_media",
            "dm_share_story",
        ):
            assert expected in names, expected
