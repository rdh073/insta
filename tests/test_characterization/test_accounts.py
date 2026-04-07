"""Characterization tests for account endpoints."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest
import services
import state


class FakeUser:
    username = "alice"
    full_name = "Alice Example"
    biography = "bio"
    follower_count = 123
    following_count = 45
    media_count = 6
    is_private = False
    is_verified = False
    is_business = True


class FakeClient:
    def __init__(self):
        self.user_id = "user-1"
        self.proxy = None
        self.loaded_settings = None
        self.request_timeout = 60
        self.delay_range = [1, 3]
        self.logged_out = False

    def set_proxy(self, proxy: str):
        self.proxy = proxy

    def set_device(self, device):
        pass

    def set_user_agent(self, ua: str):
        pass

    def load_settings(self, path):
        self.loaded_settings = path

    def login(self, username: str, password: str, **kwargs):
        self.username = username
        self.password = password

    def dump_settings(self, path):
        path.write_text(json.dumps({"session": self.username}))

    def user_info(self, _user_id: str):
        return FakeUser()

    def logout(self):
        self.logged_out = True


def test_login_account_success(monkeypatch):
    """Login endpoint returns active account."""
    import instagram

    monkeypatch.setattr(instagram, "IGClient", FakeClient)

    result = services.login_account("alice", "secret", "http://proxy:8080")

    assert result["username"] == "alice"
    assert result["status"] == "active"
    assert "id" in result
    # followers enrichment happens via background task, not in login_account itself


def test_login_account_already_logged_in(monkeypatch):
    """Login when already logged in returns existing account."""
    import instagram

    monkeypatch.setattr(instagram, "IGClient", FakeClient)

    # First login
    first = services.login_account("alice", "secret")
    account_id = first["id"]

    # Second login same username
    second = services.login_account("alice", "secret")

    assert second["id"] == account_id
    assert second["status"] == "active"


def test_logout_account_success(monkeypatch):
    """Logout endpoint removes account and returns removed status."""
    import instagram

    monkeypatch.setattr(instagram, "IGClient", FakeClient)

    # First login
    result = services.login_account("alice", "secret")
    account_id = result["id"]

    # Then logout
    logout_result = services.logout_account(account_id)

    assert logout_result["id"] == account_id
    assert logout_result["status"] == "removed"
    assert logout_result["username"] == "alice"


def test_logout_account_not_found():
    """Logout non-existent account raises ValueError."""
    with pytest.raises(ValueError, match="Account not found"):
        services.logout_account("nonexistent")


def test_set_proxy_success(monkeypatch):
    """Set proxy endpoint updates account proxy."""
    import instagram

    monkeypatch.setattr(instagram, "IGClient", FakeClient)

    # Login first
    result = services.login_account("alice", "secret")
    account_id = result["id"]

    # Set proxy
    proxy_result = services.set_account_proxy(account_id, "socks5://127.0.0.1:9000")

    assert proxy_result["proxy"] == "socks5://127.0.0.1:9000"
    assert proxy_result["status"] == "active"
    assert (state.get_account(account_id) or {})["proxy"] == "socks5://127.0.0.1:9000"


def test_set_proxy_not_found():
    """Set proxy on non-existent account raises ValueError."""
    with pytest.raises(ValueError, match="Account not found"):
        services.set_account_proxy("nonexistent", "http://proxy:8080")


def test_list_accounts_returns_all():
    """List accounts returns all with status and metadata."""
    state.set_account("acct-1", {
        "username": "alice",
        "password": "secret",
        "proxy": None,
        "full_name": "Alice Example",
        "followers": 100,
        "following": 50,
    })
    state.set_account_status("acct-1", "idle")

    result = services.list_accounts_data()

    assert len(result) >= 1
    accounts_dict = {a["id"]: a for a in result}
    assert "acct-1" in accounts_dict
    assert accounts_dict["acct-1"]["username"] == "alice"
    assert accounts_dict["acct-1"]["status"] == "idle"


def test_bulk_logout_accounts(monkeypatch):
    """Bulk logout removes multiple accounts."""
    import instagram

    monkeypatch.setattr(instagram, "IGClient", FakeClient)

    # Create accounts
    acc1 = services.login_account("alice", "secret")
    acc2 = services.login_account("bob", "secret")

    # Bulk logout
    results = services.bulk_logout_accounts([acc1["id"], acc2["id"]])

    assert len(results) == 2
    assert all(r["status"] == "removed" for r in results)
    assert {r["username"] for r in results} == {"alice", "bob"}


def test_bulk_logout_with_missing_account():
    """Bulk logout handles missing accounts gracefully."""
    results = services.bulk_logout_accounts(["nonexistent1", "nonexistent2"])

    assert len(results) == 2
    assert all(r["status"] == "not_found" for r in results)
