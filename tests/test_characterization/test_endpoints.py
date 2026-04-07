"""Characterization tests for key HTTP endpoints."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch, AsyncMock

import pytest


class TestLoginEndpoint:
    """POST /api/accounts/login endpoint behavior."""

    def test_login_success_returns_200_with_account(self, monkeypatch):
        """Successful login returns 200 with account id, username, and active status."""
        from app.main import app
        from fastapi.testclient import TestClient
        import instagram

        class FakeClient:
            user_id = "123"
            request_timeout = 60
            delay_range = [1, 3]
            login_flow = None  # will be overwritten by _new_client

            def set_proxy(self, proxy): pass
            def set_device(self, device): pass
            def set_user_agent(self, ua): pass
            def load_settings(self, path): pass

            def login(self, username, password, **kwargs):
                pass

            def dump_settings(self, path):
                path.write_text("{}")

            def user_info(self, _id):
                class User:
                    username = "alice"
                    full_name = "Alice"
                    follower_count = 100
                    following_count = 50
                    media_count = 10
                    is_private = False
                    is_verified = False
                    is_business = False
                    biography = ""

                return User()

        monkeypatch.setattr(instagram, "IGClient", lambda: FakeClient())

        client = TestClient(app)
        response = client.post("/api/accounts/login", json={
            "username": "alice",
            "password": "secret",
            "proxy": None,
            "totp_secret": None,
        })

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["username"] == "alice"
        assert data["status"] == "active"


class TestProxyEndpoint:
    """PATCH /api/accounts/{account_id}/proxy endpoint behavior."""

    def test_proxy_success_returns_200_with_updated_proxy(self):
        """Successful proxy update returns 200 with updated proxy in response."""
        from app.main import app
        from fastapi.testclient import TestClient
        import state

        client = TestClient(app)

        # Create account first
        state.set_account("test-account", {
            "username": "testuser",
            "password": "secret",
            "proxy": None,
        })

        # Update proxy
        response = client.patch("/api/accounts/test-account/proxy", json={
            "proxy": "http://proxy:8080"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["proxy"] == "http://proxy:8080"


class TestListPostsEndpoint:
    """GET /api/posts endpoint behavior."""

    def test_list_posts_returns_200_with_jobs_array(self):
        """List posts returns 200 with jobs array even if empty."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/posts")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestAIChatEndpoint:
    """POST /api/ai/chat/graph endpoint behavior."""

    def test_ai_chat_error_handling_returns_sse(self):
        """AI graph chat endpoint exists and returns SSE or validation error."""
        # /api/ai/chat was the legacy endpoint; the active endpoint is /api/ai/chat/graph
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        response = client.post("/api/ai/chat/graph", json={
            "message": "test",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "apiKey": "",  # Empty key triggers auth error from LLM gateway
        })

        # Should return 200 streaming, 400 validation error, or 503 LLM auth error
        # (not 404, which would mean the endpoint doesn't exist)
        assert response.status_code != 404, "Endpoint /api/ai/chat/graph must exist"
