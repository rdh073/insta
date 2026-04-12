"""Contract tests for direct-search HTTP serialization and route wiring."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from app.application.dto.instagram_direct_dto import DirectSearchUserSummary

_MAPPERS_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "adapters"
    / "http"
    / "routers"
    / "instagram"
    / "mappers.py"
)
_DIRECT_ROUTER_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "adapters"
    / "http"
    / "routers"
    / "instagram"
    / "direct.py"
)

_MAPPERS_SPEC = importlib.util.spec_from_file_location("direct_mappers_under_test", _MAPPERS_PATH)
assert _MAPPERS_SPEC and _MAPPERS_SPEC.loader
_MAPPERS_MODULE = importlib.util.module_from_spec(_MAPPERS_SPEC)
sys.modules[_MAPPERS_SPEC.name] = _MAPPERS_MODULE
_MAPPERS_SPEC.loader.exec_module(_MAPPERS_MODULE)
_to_direct_search_user = _MAPPERS_MODULE._to_direct_search_user


def test_direct_search_user_mapper_shape_is_stable():
    """Mapper must expose a user-centric payload, not thread-centric fields."""
    dto = DirectSearchUserSummary(
        user_id=123,
        username="john",
        full_name="John Doe",
        profile_pic_url="https://example.com/john.jpg",
        is_private=False,
        is_verified=True,
    )

    payload = _to_direct_search_user(dto)

    assert payload == {
        "userId": 123,
        "username": "john",
        "fullName": "John Doe",
        "profilePicUrl": "https://example.com/john.jpg",
        "isPrivate": False,
        "isVerified": True,
    }
    assert "directThreadId" not in payload


def test_search_route_is_wired_to_user_contract():
    """Route implementation should return `users` mapped by _to_direct_search_user."""
    content = _DIRECT_ROUTER_PATH.read_text()
    function_start = content.index("def search_direct_threads(")
    function_source = content[function_start:]

    assert '"users": [_to_direct_search_user(user) for user in users]' in function_source
    assert '"threads": [_to_direct_thread_summary(t) for t in threads]' not in function_source
