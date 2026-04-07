"""Sliding-window rate limiter middleware.

Tracks request counts per client IP in a fixed-size time window.
Rejects excess requests with 429 Too Many Requests.

No external dependencies — uses an in-memory dict with automatic cleanup.
For multi-process production, replace with Redis-backed implementation.

Configuration via environment:
    APP_RATE_LIMIT_RPM          — requests per minute per IP (0 = disabled)
    APP_RATE_LIMIT_BURST        — extra burst allowance above RPM
    APP_RATE_LIMIT_EXCLUDE_PATHS — comma-separated paths exempt from limiting
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("instamanager.ratelimit")

# ── Configuration ────────────────────────────────────────────────────────────

_DEFAULT_RPM = 120
_DEFAULT_BURST = 20
_DEFAULT_EXCLUDE = "/health,/docs,/openapi.json,/redoc"
_WINDOW_SECONDS = 60


@dataclass(frozen=True)
class RateLimitSettings:
    rpm: int
    burst: int
    exclude_paths: frozenset[str]

    @property
    def enabled(self) -> bool:
        return self.rpm > 0


def load_rate_limit_settings() -> RateLimitSettings:
    rpm = int(os.getenv("APP_RATE_LIMIT_RPM", str(_DEFAULT_RPM)))
    burst = int(os.getenv("APP_RATE_LIMIT_BURST", str(_DEFAULT_BURST)))
    raw_exclude = os.getenv("APP_RATE_LIMIT_EXCLUDE_PATHS", _DEFAULT_EXCLUDE)
    exclude = frozenset(p.strip() for p in raw_exclude.split(",") if p.strip())
    return RateLimitSettings(rpm=rpm, burst=burst, exclude_paths=exclude)


# ── Sliding window tracker ───────────────────────────────────────────────────


class _SlidingWindowCounter:
    """Per-IP request counter with automatic stale entry cleanup.

    Uses two half-windows for smooth sliding behavior instead of hard resets.
    """

    def __init__(self, window: float = _WINDOW_SECONDS):
        self._window = window
        self._half = window / 2
        # {client_key: [current_count, previous_count, current_window_start]}
        self._buckets: dict[str, list] = defaultdict(lambda: [0, 0, 0.0])
        self._last_cleanup = time.monotonic()
        self._lock = threading.Lock()

    def hit(self, key: str) -> float:
        """Record a request and return the estimated rate for the current window."""
        with self._lock:
            now = time.monotonic()
            bucket = self._buckets[key]
            current_count, prev_count, window_start = bucket

            elapsed = now - window_start
            if elapsed >= self._window:
                bucket[1] = current_count
                bucket[0] = 1
                bucket[2] = now
            elif elapsed >= self._half:
                bucket[1] = current_count
                bucket[0] = 1
                bucket[2] = now
            else:
                bucket[0] = current_count + 1

            weight = max(0.0, 1.0 - (now - bucket[2]) / self._window)
            rate = bucket[0] + bucket[1] * weight

            if now - self._last_cleanup > 300:
                self._cleanup(now)

            return rate

    def _cleanup(self, now: float) -> None:
        """Remove stale entries. Must be called under self._lock."""
        stale_threshold = now - self._window * 3
        stale_keys = [k for k, v in self._buckets.items() if v[2] < stale_threshold]
        for k in stale_keys:
            del self._buckets[k]
        self._last_cleanup = now
        if stale_keys:
            logger.debug("rate_limit.cleanup removed=%d remaining=%d", len(stale_keys), len(self._buckets))


# ── Middleware ────────────────────────────────────────────────────────────────

_counter = _SlidingWindowCounter()


def _client_key(request: Request) -> str:
    """Extract client identifier for rate limiting."""
    # Respect X-Forwarded-For when behind a reverse proxy
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def register_rate_limit(app: FastAPI, settings: RateLimitSettings) -> None:
    """Attach rate limiting middleware to the FastAPI app."""
    if not settings.enabled:
        logger.info("rate_limit.disabled rpm=0")
        return

    limit = settings.rpm + settings.burst

    logger.info(
        "rate_limit.enabled rpm=%d burst=%d total_limit=%d exclude=%s",
        settings.rpm, settings.burst, limit, ",".join(sorted(settings.exclude_paths)),
    )

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        path = request.url.path

        # Skip excluded paths
        if path in settings.exclude_paths:
            return await call_next(request)

        # Skip preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        client = _client_key(request)
        rate = _counter.hit(client)

        if rate > limit:
            retry_after = int(_WINDOW_SECONDS / 2)
            logger.warning(
                "rate_limit.exceeded client=%s path=%s rate=%.0f limit=%d",
                client, path, rate, limit,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(settings.rpm),
                    "X-RateLimit-Remaining": str(max(0, int(limit - rate))),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(settings.rpm)
        response.headers["X-RateLimit-Remaining"] = str(max(0, int(limit - rate)))
        return response

    return None
