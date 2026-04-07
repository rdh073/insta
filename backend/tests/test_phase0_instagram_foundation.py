"""Phase 0 tests: Instagram foundation seams and transport ownership."""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app


def test_container_exposes_identity_and_relationship_usecases():
    """Container should provide application seams for identity/relationships."""
    from app.bootstrap.container import create_services

    services = create_services()
    assert "identity" in services
    assert "relationships" in services
    assert services["identity"] is not None
    assert services["relationships"] is not None


def test_dependencies_expose_identity_and_relationship_usecases():
    """HTTP dependencies should expose new application seams."""
    from app.adapters.http import dependencies

    assert hasattr(dependencies, "get_identity_usecases")
    assert hasattr(dependencies, "get_relationship_usecases")


def test_instagram_transport_router_is_registered():
    """App should register /api/instagram transport owner routes."""
    paths = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute) and "GET" in route.methods
    }
    assert "/api/instagram/capabilities" in paths
    assert "/api/instagram/identity/{account_id}/me" in paths
    assert "/api/instagram/relationships/{account_id}/followers" in paths
    assert "/api/instagram/relationships/{account_id}/following" in paths


def test_instagram_router_depends_on_usecases_not_vendor_adapters():
    """Router must depend on dependency getters, not concrete Instagram adapters."""
    with open("/home/xtrzy/Workspace/insta/backend/app/adapters/http/routers/instagram.py") as f:
        content = f.read()

    assert "get_identity_usecases" in content
    assert "get_relationship_usecases" in content
    assert "from app.adapters.instagram" not in content


def test_instagram_write_envelope_contract_exists():
    """Phase 0 should define write-envelope schema contracts."""
    from app.adapters.http.schemas.instagram import (
        InstagramWriteEnvelope,
        StoryPublishEnvelope,
        CommentCreateEnvelope,
        DirectSendEnvelope,
    )

    assert InstagramWriteEnvelope is not None
    assert StoryPublishEnvelope is not None
    assert CommentCreateEnvelope is not None
    assert DirectSendEnvelope is not None
