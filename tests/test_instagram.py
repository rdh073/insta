from __future__ import annotations

import json

import instagram
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
        self.logged_out = False
        self.request_timeout = 60
        self.delay_range = [1, 3]

    def set_proxy(self, proxy: str):
        self.proxy = proxy

    def set_device(self, _device: dict) -> None:
        pass

    def set_user_agent(self, _ua: str) -> None:
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


def test_create_authenticated_client_retries_with_fresh_client(monkeypatch):
    created_clients: list[RetryClient] = []

    class RetryClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.should_fail = not created_clients
            created_clients.append(self)

        def login(self, username: str, password: str, **kwargs):
            super().login(username, password)
            if self.should_fail:
                raise instagram.LoginRequired()

    monkeypatch.setattr(instagram, "IGClient", RetryClient)
    (instagram.SESSIONS_DIR / "alice.json").write_text(json.dumps({"session": "stale"}))

    client = instagram.create_authenticated_client("alice", "secret", "http://proxy:8080")

    assert client is created_clients[1]
    assert len(created_clients) == 2
    assert created_clients[0].proxy == "http://proxy:8080"
    assert created_clients[1].proxy == "http://proxy:8080"
    assert (instagram.SESSIONS_DIR / "alice.json").exists()


def test_relogin_account_sync_replaces_stale_client_and_updates_state(monkeypatch):
    monkeypatch.setattr(instagram, "IGClient", FakeClient)

    stale_client = FakeClient()
    state.set_account("acct-1", {
        "username": "alice",
        "password": "secret",
        "proxy": "http://proxy:8080",
    })
    state.set_client("acct-1", stale_client)

    result = instagram.relogin_account_sync(
        "acct-1",
        username="alice",
        password="secret",
        proxy="http://proxy:8080",
    )

    # stale client reference is dropped (pop_client) but NOT logged out —
    # calling logout() would invalidate the server-side session file we reuse.
    assert stale_client.logged_out is False
    assert isinstance(state.get_client("acct-1"), FakeClient)
    assert state.get_client("acct-1") is not stale_client
    assert state.get_account_status_value("acct-1") == "active"
    # followers enrichment happens via background task, not during relogin
    assert result["status"] == "active"
