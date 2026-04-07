"""OpenAI Codex OAuth credential manager.

Provides PKCE helpers, authorization URL building, refresh-token exchange, and
runtime access-token resolution for the Codex provider.
"""

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


_DEFAULT_AUTH_ENDPOINT = "https://auth.openai.com/oauth/authorize"
_DEFAULT_TOKEN_ENDPOINT = "https://auth.openai.com/oauth/token"
_DEFAULT_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
_DEFAULT_REDIRECT_URI = "http://localhost:1455/auth/callback"
_DEFAULT_SCOPE = "openid profile email offline_access"


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _decode_jwt_payload(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        raw = base64.urlsafe_b64decode(payload_b64 + padding)
        parsed = json.loads(raw.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def extract_account_id(tokens: dict[str, str]) -> str | None:
    """Extract ChatGPT account id from id_token/access_token JWT claims."""
    for field in ("id_token", "access_token"):
        token = tokens.get(field)
        if not token:
            continue
        claims = _decode_jwt_payload(token)
        if not claims:
            continue
        if isinstance(claims.get("chatgpt_account_id"), str):
            return claims["chatgpt_account_id"]
        auth_claim = claims.get("https://api.openai.com/auth")
        if isinstance(auth_claim, dict) and isinstance(auth_claim.get("chatgpt_account_id"), str):
            return auth_claim["chatgpt_account_id"]
        orgs = claims.get("organizations")
        if isinstance(orgs, list) and orgs:
            first = orgs[0]
            if isinstance(first, dict) and isinstance(first.get("id"), str):
                return first["id"]
    return None


@dataclass
class CodexTokenBundle:
    access_token: str
    refresh_token: str | None
    expires_at_ms: int
    account_id: str | None = None


class CodexOAuthError(RuntimeError):
    """Codex OAuth failure with optional status and OAuth error code."""

    def __init__(self, message: str, *, status: int | None = None, error_code: str | None = None):
        super().__init__(message)
        self.status = status
        self.error_code = error_code

    def is_likely_invalid_grant(self) -> bool:
        if self.error_code and "invalid_grant" in self.error_code.lower():
            return True
        if self.status in {400, 401, 403} and "invalid_grant" in str(self).lower():
            return True
        return False


class CodexOAuthClient:
    """Manages OAuth credentials for OpenAI Codex."""

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
        self._cached: CodexTokenBundle | None = None
        self._token_store = token_store
        self._provider = "openai_codex"

    @staticmethod
    def generate_code_verifier() -> str:
        """Generate PKCE code verifier."""
        return _base64url(secrets.token_bytes(32))

    @staticmethod
    def generate_code_challenge(verifier: str) -> str:
        """Generate PKCE code challenge (S256)."""
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return _base64url(digest)

    @staticmethod
    def generate_state() -> str:
        return secrets.token_hex(16)

    def build_authorization_url(self, code_challenge: str, state: str) -> str:
        """Build OpenAI Codex OAuth authorization URL."""
        params = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": self.scope,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "response_type": "code",
                "state": state,
                "id_token_add_organizations": "true",
                "codex_cli_simplified_flow": "true",
                "originator": "codex_cli_rs",
            }
        )
        return f"{self.auth_endpoint}?{params}"

    def get_account_id(self) -> str | None:
        if self._cached and self._cached.account_id:
            return self._cached.account_id
        account_id = os.getenv("OPENAI_CODEX_ACCOUNT_ID", "").strip()
        return account_id or None

    async def get_access_token(self) -> str:
        """Get valid access token, refreshing if needed."""
        now_ms = int(time.time() * 1000)
        # explicit runtime override
        env_access = os.getenv("OPENAI_CODEX_ACCESS_TOKEN", "").strip()
        if env_access:
            expires_s = os.getenv("OPENAI_CODEX_EXPIRES_AT", "").strip()
            expires_ms = int(expires_s) * 1000 if expires_s.isdigit() else now_ms + 5 * 60 * 1000
            account_id = os.getenv("OPENAI_CODEX_ACCOUNT_ID", "").strip() or extract_account_id(
                {"access_token": env_access}
            )
            self._cached = CodexTokenBundle(
                access_token=env_access,
                refresh_token=os.getenv("OPENAI_CODEX_REFRESH_TOKEN", "").strip() or None,
                expires_at_ms=expires_ms,
                account_id=account_id,
            )
            return env_access

        if self._cached is None and self._token_store is not None:
            stored = self._token_store.get(self._provider)
            if stored is not None:
                self._cached = CodexTokenBundle(
                    access_token=stored.access_token or "",
                    refresh_token=stored.refresh_token,
                    expires_at_ms=stored.expires_at_ms or 0,
                    account_id=stored.account_id,
                )

        if self._cached and self._cached.access_token and self._cached.expires_at_ms - now_ms > 30_000:
            return self._cached.access_token

        return await self.refresh_token()

    async def refresh_token(self) -> str:
        """Refresh access token using stored refresh token."""
        refresh_token = None
        if self._cached and self._cached.refresh_token:
            refresh_token = self._cached.refresh_token
        if not refresh_token:
            refresh_token = os.getenv("OPENAI_CODEX_REFRESH_TOKEN", "").strip()
        if not refresh_token:
            raise CodexOAuthError(
                "Codex OAuth refresh_token is missing. Set OPENAI_CODEX_REFRESH_TOKEN or provide OPENAI_CODEX_ACCESS_TOKEN."
            )

        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": refresh_token,
        }
        token_data = await asyncio.to_thread(self._post_json, self.token_endpoint, payload)

        access_token = str(token_data.get("access_token") or "").strip()
        if not access_token:
            raise CodexOAuthError("OAuth token refresh response missing access_token")

        next_refresh_token = str(token_data.get("refresh_token") or "").strip() or refresh_token
        expires_in = int(token_data.get("expires_in") or 0)
        now_ms = int(time.time() * 1000)
        expires_at_ms = now_ms + max(expires_in, 60) * 1000
        account_id = extract_account_id(
            {
                "id_token": str(token_data.get("id_token") or ""),
                "access_token": access_token,
            }
        ) or (self._cached.account_id if self._cached else None)

        self._cached = CodexTokenBundle(
            access_token=access_token,
            refresh_token=next_refresh_token,
            expires_at_ms=expires_at_ms,
            account_id=account_id,
        )
        if self._token_store is not None:
            self._token_store.save(
                OAuthCredential(
                    provider=self._provider,
                    refresh_token=next_refresh_token,
                    access_token=access_token,
                    expires_at_ms=expires_at_ms,
                    account_id=account_id,
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
        """Exchange OAuth authorization code for access/refresh token bundle."""
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": self.redirect_uri,
        }
        token_data = await asyncio.to_thread(self._post_json, self.token_endpoint, payload)

        access_token = str(token_data.get("access_token") or "").strip()
        refresh_token = str(token_data.get("refresh_token") or "").strip()
        if not access_token:
            raise CodexOAuthError("OAuth token exchange response missing access_token")
        if not refresh_token:
            raise CodexOAuthError("OAuth token exchange response missing refresh_token")

        expires_in = int(token_data.get("expires_in") or 0)
        now_ms = int(time.time() * 1000)
        expires_at_ms = now_ms + max(expires_in, 60) * 1000
        account_id = extract_account_id(
            {
                "id_token": str(token_data.get("id_token") or ""),
                "access_token": access_token,
            }
        )
        self._cached = CodexTokenBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at_ms=expires_at_ms,
            account_id=account_id,
        )
        if self._token_store is not None:
            self._token_store.save(
                OAuthCredential(
                    provider=self._provider,
                    refresh_token=refresh_token,
                    access_token=access_token,
                    expires_at_ms=expires_at_ms,
                    account_id=account_id,
                )
            )
        return access_token

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Perform blocking form-encoded POST request and return parsed body.

        OpenAI token endpoint requires application/x-www-form-urlencoded, not JSON.
        """
        body = urllib.parse.urlencode(payload).encode("ascii")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        timeout_s = float(os.getenv("OPENAI_CODEX_OAUTH_TIMEOUT_SECONDS", "30"))
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
                if not isinstance(data, dict):
                    raise CodexOAuthError("OAuth response is not a JSON object")
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
            raise CodexOAuthError(
                f"Codex OAuth token exchange failed: {exc.code} {error_message}",
                status=exc.code,
                error_code=error_code,
            ) from exc
        except urllib.error.URLError as exc:
            raise CodexOAuthError(f"Codex OAuth network error: {exc.reason}") from exc
