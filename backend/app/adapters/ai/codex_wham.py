"""OpenAI Codex WHAM usage client.

Fetches usage/rate-limit metadata for Codex from ChatGPT backend API.
This module is optional telemetry and should never break request flow.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


_DEFAULT_WHAM_URL = "https://chatgpt.com/backend-api/wham/usage"


@dataclass(frozen=True)
class CodexRateLimitWindow:
    used_percent: float
    window_minutes: int | None = None
    resets_at_ms: int | None = None


@dataclass(frozen=True)
class CodexRateLimitInfo:
    fetched_at_ms: int
    primary: CodexRateLimitWindow | None = None
    secondary: CodexRateLimitWindow | None = None
    plan_type: str | None = None


class CodexWHAMClient:
    """Fetches and parses Codex usage/rate-limit information."""

    def __init__(self, wham_url: str = _DEFAULT_WHAM_URL) -> None:
        self.wham_url = wham_url

    async def fetch_usage(
        self,
        access_token: str,
        *,
        account_id: str | None = None,
    ) -> CodexRateLimitInfo:
        fetched_at_ms = int(time.time() * 1000)
        payload = await asyncio.to_thread(self._get_json, access_token, account_id)
        return parse_openai_codex_usage_payload(payload, fetched_at_ms=fetched_at_ms)

    def _get_json(self, access_token: str, account_id: str | None) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        if account_id:
            headers["ChatGPT-Account-Id"] = account_id
        request = urllib.request.Request(
            self.wham_url,
            headers=headers,
            method="GET",
        )
        timeout_s = float(os.getenv("OPENAI_CODEX_WHAM_TIMEOUT_SECONDS", "20"))
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
                return data if isinstance(data, dict) else {}
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"WHAM usage request failed: {exc.code} {text[:180]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"WHAM usage network error: {exc.reason}") from exc


def _clamp_percent(value: float) -> float:
    if value != value:  # NaN
        return 0.0
    return max(0.0, min(100.0, float(value)))


def _seconds_to_ms(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return int(round(float(value) * 1000))
    return None


def _parse_window(raw: Any) -> CodexRateLimitWindow | None:
    if not isinstance(raw, dict):
        return None
    used_percent = raw.get("used_percent")
    if not isinstance(used_percent, (int, float)):
        return None
    window_seconds = raw.get("limit_window_seconds")
    return CodexRateLimitWindow(
        used_percent=_clamp_percent(float(used_percent)),
        window_minutes=int(round(window_seconds / 60))
        if isinstance(window_seconds, (int, float))
        else None,
        resets_at_ms=_seconds_to_ms(raw.get("reset_at")),
    )


def parse_openai_codex_usage_payload(payload: Any, *, fetched_at_ms: int) -> CodexRateLimitInfo:
    """Parse WHAM usage payload into stable dataclass."""
    data = payload if isinstance(payload, dict) else {}
    rate_limit = data.get("rate_limit")
    primary_raw = rate_limit.get("primary_window") if isinstance(rate_limit, dict) else None
    secondary_raw = rate_limit.get("secondary_window") if isinstance(rate_limit, dict) else None

    plan_type = data.get("plan_type") if isinstance(data.get("plan_type"), str) else None
    return CodexRateLimitInfo(
        fetched_at_ms=fetched_at_ms,
        primary=_parse_window(primary_raw),
        secondary=_parse_window(secondary_raw),
        plan_type=plan_type,
    )
