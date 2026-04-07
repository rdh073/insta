"""File-based OAuth token store — durable without requiring SQL or encryption keys.

Stores credentials as plain JSON in a local file (sessions/oauth_tokens.json by
default).  Suitable for single-node deployments where SQL persistence is not
configured.  Tokens are stored unencrypted, so the file should have restrictive
permissions (0o600) and must not be committed to version control.
"""

from __future__ import annotations

import json
import os
import stat
import threading
from pathlib import Path
from typing import Any

from app.adapters.ai.oauth_token_store import OAuthCredential, OAuthTokenStore

_DEFAULT_PATH = Path(__file__).parent.parent.parent.parent / "sessions" / "oauth_tokens.json"


class FileOAuthTokenStore(OAuthTokenStore):
    """Persists OAuth credentials to a JSON file on disk.

    Thread-safe via a reentrant lock.  All reads and writes reload/flush the
    full file so that multiple processes sharing the same file path see a
    consistent state (last-write-wins per provider).
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else Path(
            os.getenv("OAUTH_TOKEN_STORE_PATH", str(_DEFAULT_PATH))
        )
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # OAuthTokenStore contract
    # ------------------------------------------------------------------

    def get(self, provider: str) -> OAuthCredential | None:
        with self._lock:
            data = self._load()
            entry = data.get(provider)
            if entry is None:
                return None
            if entry.get("revoked"):
                return None
            return OAuthCredential(
                provider=entry["provider"],
                refresh_token=entry["refresh_token"],
                access_token=entry.get("access_token") or None,
                expires_at_ms=entry.get("expires_at_ms"),
                account_id=entry.get("account_id"),
                revoked=bool(entry.get("revoked")),
            )

    def save(self, credential: OAuthCredential) -> None:
        with self._lock:
            data = self._load()
            data[credential.provider] = {
                "provider": credential.provider,
                "refresh_token": credential.refresh_token,
                "access_token": credential.access_token,
                "expires_at_ms": credential.expires_at_ms,
                "account_id": credential.account_id,
                "revoked": credential.revoked,
            }
            self._dump(data)

    def revoke(self, provider: str) -> None:
        with self._lock:
            data = self._load()
            entry = data.get(provider)
            if entry is None:
                return
            entry["revoked"] = True
            self._dump(data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            text = self._path.read_text(encoding="utf-8")
            parsed = json.loads(text) if text.strip() else {}
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _dump(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        # Restrict permissions before moving into place
        try:
            os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        tmp.replace(self._path)
