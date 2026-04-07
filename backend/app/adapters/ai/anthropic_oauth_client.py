"""Anthropic OAuth credential manager for Claude Code."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .oauth_token_store import OAuthCredential, OAuthTokenStore


_DEFAULT_AUTH_ENDPOINT = "https://claude.ai/oauth/authorize"
_DEFAULT_TOKEN_ENDPOINT = "https://console.anthropic.com/v1/oauth/token"
_DEFAULT_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
_DEFAULT_REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"
_DEFAULT_SCOPE = "org:create_api_key user:profile user:inference"


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


@dataclass
class AnthropicTokenBundle:
    access_token: str
    refresh_token: str | None
    expires_at_ms: int


class AnthropicOAuthError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, error_code: str | None = None):
        super().__init__(message)
        self.status = status
        self.error_code = error_code

    def is_likely_invalid_grant(self) -> bool:
        if self.error_code and "invalid_grant" in self.error_code.lower():
            return True
        return self.status in {400, 401, 403} and "invalid_grant" in str(self).lower()


class AnthropicOAuthClient:
    """Manages OAuth credentials for Anthropic Claude Code."""

    def __init__(
        self,
        *,
        auth_endpoint: str = _DEFAULT_AUTH_ENDPOINT,
        token_endpoint: str = _DEFAULT_TOKEN_ENDPOINT,
        client_id: str = _DEFAULT_CLIENT_ID,
        redirect_uri: str = _DEFAULT_REDIRECT_URI,
        scope: str = _DEFAULT_SCOPE,
        token_store: OAuthTokenStore | None = None,
    ) -> None:
        self.auth_endpoint = auth_endpoint
        self.token_endpoint = token_endpoint
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scope = scope
        self._cached: AnthropicTokenBundle | None = None
        self._token_store = token_store
        self._provider = "claude_code"

    @staticmethod
    def generate_state() -> str:
        return secrets.token_hex(16)

    @staticmethod
    def generate_code_verifier() -> str:
        return _base64url(secrets.token_bytes(32))

    @staticmethod
    def generate_code_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return _base64url(digest)

    def build_authorization_url(self, *, code_challenge: str, state: str) -> str:
        params = urllib.parse.urlencode(
            {
                "code": "true",
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "scope": self.scope,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "state": state,
            }
        )
        return f"{self.auth_endpoint}?{params}"

    async def get_access_token(self) -> str:
        now_ms = int(time.time() * 1000)
        env_access = os.getenv("CLAUDE_CODE_ACCESS_TOKEN", "").strip()
        if env_access:
            expires_s = os.getenv("CLAUDE_CODE_EXPIRES_AT", "").strip()
            expires_ms = int(expires_s) * 1000 if expires_s.isdigit() else now_ms + 5 * 60 * 1000
            self._cached = AnthropicTokenBundle(
                access_token=env_access,
                refresh_token=os.getenv("CLAUDE_CODE_REFRESH_TOKEN", "").strip() or None,
                expires_at_ms=expires_ms,
            )
            return env_access

        if self._cached is None and self._token_store is not None:
            stored = self._token_store.get(self._provider)
            if stored is not None:
                self._cached = AnthropicTokenBundle(
                    access_token=stored.access_token or "",
                    refresh_token=stored.refresh_token,
                    expires_at_ms=stored.expires_at_ms or 0,
                )

        if self._cached and self._cached.access_token and self._cached.expires_at_ms - now_ms > 30_000:
            return self._cached.access_token

        return await self.refresh_token()

    async def refresh_token(self) -> str:
        refresh_token = self._cached.refresh_token if self._cached else None
        if not refresh_token:
            refresh_token = os.getenv("CLAUDE_CODE_REFRESH_TOKEN", "").strip()
        if not refresh_token:
            raise AnthropicOAuthError(
                "Claude Code OAuth refresh_token is missing. Set CLAUDE_CODE_REFRESH_TOKEN or provide CLAUDE_CODE_ACCESS_TOKEN."
            )

        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": refresh_token,
        }
        token_data = await asyncio.to_thread(self._post_json, self.token_endpoint, payload)

        access_token = str(token_data.get("access_token") or "").strip()
        if not access_token:
            raise AnthropicOAuthError("OAuth token refresh response missing access_token")

        next_refresh = str(token_data.get("refresh_token") or "").strip() or refresh_token
        expires_in = int(token_data.get("expires_in") or 0)
        now_ms = int(time.time() * 1000)
        expires_at_ms = now_ms + max(expires_in, 60) * 1000
        self._cached = AnthropicTokenBundle(
            access_token=access_token,
            refresh_token=next_refresh,
            expires_at_ms=expires_at_ms,
        )
        if self._token_store is not None:
            self._token_store.save(
                OAuthCredential(
                    provider=self._provider,
                    refresh_token=next_refresh,
                    access_token=access_token,
                    expires_at_ms=expires_at_ms,
                )
            )
        return access_token

    async def exchange_authorization_code(
        self,
        *,
        code: str,
        code_verifier: str,
        state: str | None = None,
    ) -> str:
        # Anthropic callback page may return code#state as a single string.
        code_parts = code.split("#")
        auth_code = code_parts[0]
        embedded_state = code_parts[1] if len(code_parts) > 1 else None

        payload = {
            "code": auth_code,
            "state": embedded_state or state,
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,
        }
        token_data = await asyncio.to_thread(self._post_json, self.token_endpoint, payload)

        access_token = str(token_data.get("access_token") or "").strip()
        refresh_token = str(token_data.get("refresh_token") or "").strip()
        if not access_token:
            raise AnthropicOAuthError("OAuth token exchange response missing access_token")
        if not refresh_token:
            raise AnthropicOAuthError("OAuth token exchange response missing refresh_token")

        expires_in = int(token_data.get("expires_in") or 0)
        now_ms = int(time.time() * 1000)
        expires_at_ms = now_ms + max(expires_in, 60) * 1000
        self._cached = AnthropicTokenBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at_ms=expires_at_ms,
        )
        if self._token_store is not None:
            self._token_store.save(
                OAuthCredential(
                    provider=self._provider,
                    refresh_token=refresh_token,
                    access_token=access_token,
                    expires_at_ms=expires_at_ms,
                )
            )
        return access_token

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "claude-code/1.0.0",
                "Accept": "application/json",
            },
            method="POST",
        )
        timeout_s = float(os.getenv("CLAUDE_CODE_OAUTH_TIMEOUT_SECONDS", "30"))
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
                if not isinstance(data, dict):
                    raise AnthropicOAuthError("OAuth response is not a JSON object")
                return data
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            error_code = None
            error_message = text
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    if isinstance(parsed.get("error"), str):
                        error_code = parsed["error"]
                    if isinstance(parsed.get("error_description"), str):
                        error_message = parsed["error_description"]
                    elif isinstance(parsed.get("message"), str):
                        error_message = parsed["message"]
            except Exception:
                pass
            raise AnthropicOAuthError(
                f"Claude OAuth token exchange failed: {exc.code} {error_message}",
                status=exc.code,
                error_code=error_code,
            ) from exc
        except urllib.error.URLError as exc:
            raise AnthropicOAuthError(f"Claude OAuth network error: {exc.reason}") from exc
