"""Phase-5 tests for durable OAuth token store with encrypted persistence."""

from __future__ import annotations

import sqlite3
import sys
import types

import pytest

# Minimal shim for backend/state.py import dependency
if "instagrapi" not in sys.modules:
    instagrapi_module = types.ModuleType("instagrapi")
    exceptions_module = types.ModuleType("instagrapi.exceptions")

    class _StubClient:  # pragma: no cover - shim class
        pass

    class _StubException(Exception):  # pragma: no cover - shim class
        pass

    instagrapi_module.Client = _StubClient
    exceptions_module.LoginRequired = _StubException
    exceptions_module.BadPassword = _StubException
    exceptions_module.ReloginAttemptExceeded = _StubException
    exceptions_module.TwoFactorRequired = _StubException
    instagrapi_module.exceptions = exceptions_module
    sys.modules["instagrapi"] = instagrapi_module
    sys.modules["instagrapi.exceptions"] = exceptions_module

pytest.importorskip("sqlalchemy")
pytest.importorskip("cryptography")

from app.adapters.ai.oauth_token_store import OAuthCredential
from app.adapters.persistence.crypto import CryptoService
from app.adapters.persistence.oauth_token_store_repository import SQLOAuthTokenStore
from app.adapters.persistence.sql_store import SqlitePersistenceStore


def test_sql_oauth_token_store_encrypts_and_recovers_tokens(tmp_path, monkeypatch):
    db_path = tmp_path / "oauth_tokens.sqlite3"
    # deterministic fernet key for test only
    monkeypatch.setenv("ENCRYPTION_KEY", "kQfQ2kGfR2r8XgEgY80qA1rQJX9uX8YfVwY0U-7kV6M=")

    store = SqlitePersistenceStore(db_path=db_path)
    crypto = CryptoService()
    token_store = SQLOAuthTokenStore(store, crypto)

    token_store.save(
        OAuthCredential(
            provider="openai_codex",
            refresh_token="refresh-secret",
            access_token="access-secret",
            expires_at_ms=1710000000000,
            account_id="acct_1",
        )
    )

    loaded = token_store.get("openai_codex")
    assert loaded is not None
    assert loaded.refresh_token == "refresh-secret"
    assert loaded.access_token == "access-secret"
    assert loaded.account_id == "acct_1"

    # raw DB must not contain plaintext tokens
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT refresh_token_encrypted, access_token_encrypted FROM oauth_credentials WHERE provider = ?",
            ("openai_codex",),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert "refresh-secret" not in (row[0] or "")
    assert "access-secret" not in (row[1] or "")


def test_sql_oauth_token_store_revoke_hides_credential(tmp_path, monkeypatch):
    db_path = tmp_path / "oauth_revoke.sqlite3"
    monkeypatch.setenv("ENCRYPTION_KEY", "kQfQ2kGfR2r8XgEgY80qA1rQJX9uX8YfVwY0U-7kV6M=")

    store = SqlitePersistenceStore(db_path=db_path)
    token_store = SQLOAuthTokenStore(store, CryptoService())

    token_store.save(
        OAuthCredential(
            provider="claude_code",
            refresh_token="refresh-claude",
            access_token="access-claude",
        )
    )
    assert token_store.get("claude_code") is not None

    token_store.revoke("claude_code")
    assert token_store.get("claude_code") is None
