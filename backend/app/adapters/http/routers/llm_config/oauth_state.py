from __future__ import annotations

import hmac
import json
import os
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256
from typing import Any

from fastapi import Request

_PROVIDER_OAUTH_STATE_TTL_MINUTES = 10


def _get_oauth_state_secret(request: Request) -> str:
    secret = getattr(request.app.state, "oauth_state_secret", "").strip()
    if secret:
        return secret

    secret = os.environ.get("OAUTH_STATE_SECRET", "").strip()
    if not secret:
        secret = os.environ.get("AUTH_SECRET", "").strip()
    if not secret:
        secret = secrets.token_urlsafe(32)

    request.app.state.oauth_state_secret = secret
    return secret


def _base64url_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return urlsafe_b64decode(data + padding)


def encode_oauth_state(
    request: Request,
    *,
    provider: str,
    frontend_redirect_uri: str,
    registered_redirect_uri: str,
    code_verifier: str,
) -> str:
    payload = {
        "sub": "provider_oauth",
        "provider": provider,
        "frontend_redirect_uri": frontend_redirect_uri,
        "registered_redirect_uri": registered_redirect_uri,
        "code_verifier": code_verifier,
        "nonce": secrets.token_hex(16),
        "iat": int(time.time()),
        "exp": int(time.time()) + (_PROVIDER_OAUTH_STATE_TTL_MINUTES * 60),
    }
    payload_segment = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        _get_oauth_state_secret(request).encode("utf-8"),
        payload_segment.encode("utf-8"),
        sha256,
    ).digest()
    return f"{payload_segment}.{_base64url_encode(signature)}"


def decode_oauth_state(token: str, request: Request, *, verify_exp: bool = True) -> dict[str, Any]:
    try:
        payload_segment, signature_segment = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Malformed OAuth state token") from exc

    expected_signature = hmac.new(
        _get_oauth_state_secret(request).encode("utf-8"),
        payload_segment.encode("utf-8"),
        sha256,
    ).digest()
    actual_signature = _base64url_decode(signature_segment)
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise ValueError("Invalid OAuth state signature")

    payload = json.loads(_base64url_decode(payload_segment).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OAuth state payload must be an object")

    required_keys = {
        "sub",
        "provider",
        "frontend_redirect_uri",
        "registered_redirect_uri",
        "code_verifier",
        "nonce",
        "exp",
    }
    missing = required_keys.difference(payload.keys())
    if missing:
        raise ValueError(f"Missing OAuth state fields: {sorted(missing)!r}")
    if payload.get("sub") != "provider_oauth":
        raise ValueError("Unexpected OAuth state subject")
    if verify_exp and int(payload["exp"]) < int(time.time()):
        raise ValueError("OAuth state expired")
    return payload
