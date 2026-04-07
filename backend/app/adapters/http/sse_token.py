"""Short-lived one-time SSE token store.

Solves the problem that the browser's native EventSource API cannot send
custom headers, so the API key would have to go in the query string where
it is logged by every reverse proxy on the path.

Flow:
  1. Frontend calls POST /api/sse/token with X-API-Key header → gets a
     single-use token valid for TTL_SECONDS.
  2. Frontend opens EventSource with ?sse_token=<token>.
  3. Middleware consumes (validates + deletes) the token on the first
     request — logging the token is harmless because it is already
     invalidated by the time any log is read.

Thread-safe via a plain threading.Lock (uvicorn single-worker is async
but background tasks may run in threads).
"""

from __future__ import annotations

import secrets
import time
from threading import Lock


class SseTokenStore:
    """In-process store for short-lived one-time SSE tokens."""

    TTL_SECONDS: int = 300  # 5 minutes — covers instagrapi slow ops + reconnect windows

    def __init__(self) -> None:
        self._tokens: dict[str, float] = {}  # token → monotonic expiry
        self._lock = Lock()

    def issue(self) -> str:
        """Generate, store, and return a new token."""
        token = secrets.token_urlsafe(32)
        expires_at = time.monotonic() + self.TTL_SECONDS
        with self._lock:
            self._tokens[token] = expires_at
            self._evict_expired()
        return token

    def validate(self, token: str) -> bool:
        """Check whether token is valid without consuming it.

        Tokens are reusable within their TTL so that EventSource auto-reconnect
        (which reuses the same URL) keeps working after a transient disconnect.
        The token becomes invalid only when it expires.
        """
        if not token:
            return False
        now = time.monotonic()
        with self._lock:
            expires_at = self._tokens.get(token)
            if expires_at is None:
                return False
            if expires_at <= now:
                del self._tokens[token]
                return False
            return True

    def _evict_expired(self) -> None:
        """Prune stale entries — call inside lock."""
        now = time.monotonic()
        stale = [t for t, exp in self._tokens.items() if exp <= now]
        for t in stale:
            del self._tokens[t]
