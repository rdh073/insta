"""Image proxy endpoint — bypasses CORP restrictions on Instagram CDN URLs.

Implements a persistent disk cache keyed by URL hash so that images survive
Instagram CDN URL expiry. Once an image is downloaded successfully it is
served from disk forever, regardless of whether the original signed URL
has since expired.
"""

from __future__ import annotations

import hashlib
import os
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/proxy", tags=["proxy"])

_ALLOWED_HOSTS = {
    "fbcdn.net",           # Facebook/Instagram CDN (all regional nodes: *.fna.fbcdn.net, etc.)
    "cdninstagram.com",    # Instagram's own CDN (scontent-*.cdninstagram.com)
    "instagram.com",
}

_CLIENT = httpx.Client(
    timeout=10,
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    },
    follow_redirects=True,
)

# Cache directory — configurable via env, defaults to storage/avatars relative
# to the process working directory (/app/ in Docker, backend/ locally).
_CACHE_DIR = Path(os.environ.get("AVATAR_CACHE_DIR", "storage/avatars"))


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def warm_image_cache(url: str) -> None:
    """Pre-fetch and persist an image URL to the local disk cache.

    Called after profile hydration so the image is stored while the signed
    CDN URL is still valid.  Silently no-ops if the image is already cached
    or if the fetch fails for any reason.
    """
    if not url:
        return
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(url)
    cache_file = _CACHE_DIR / f"{key}.bin"
    if cache_file.exists():
        return  # already cached
    try:
        resp = _CLIENT.get(url)
        if resp.is_success:
            content_type = resp.headers.get("content-type", "image/jpeg")
            cache_file.write_bytes(resp.content)
            (_CACHE_DIR / f"{key}.ct").write_text(content_type)
            logger.debug("Avatar cached: %s bytes for hash %s", len(resp.content), key[:12])
        else:
            logger.debug("Avatar warm-cache skipped (HTTP %s) for hash %s", resp.status_code, key[:12])
    except Exception as exc:
        logger.debug("Avatar warm-cache error: %s", exc)


@router.get("/image")
def proxy_image(url: str = Query(...)):
    """Proxy an Instagram CDN image to avoid CORP browser blocks.

    Serves from local disk cache when available (survives CDN URL expiry).
    On a cache miss the image is fetched from the CDN, cached, then returned.
    Returns 404 (not 502) when the CDN URL has expired so the browser falls
    back to the initials avatar cleanly.
    """
    from urllib.parse import urlparse

    host = urlparse(url).netloc
    if not any(host == h or host.endswith("." + h) for h in _ALLOWED_HOSTS):
        raise HTTPException(status_code=400, detail="URL not allowed")

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(url)
    cache_file = _CACHE_DIR / f"{key}.bin"
    ct_file = _CACHE_DIR / f"{key}.ct"

    # Serve from cache if available
    if cache_file.exists():
        content_type = ct_file.read_text() if ct_file.exists() else "image/jpeg"
        return Response(
            content=cache_file.read_bytes(),
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=2592000"},  # 30 days
        )

    # Cache miss — fetch from CDN
    try:
        resp = _CLIENT.get(url)
        resp.raise_for_status()
    except httpx.HTTPStatusError:
        # CDN URL has expired — return 404 so the browser shows initials fallback
        raise HTTPException(status_code=404, detail="Image not found or URL expired")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    content_type = resp.headers.get("content-type", "image/jpeg")
    # Persist to disk so future requests survive CDN URL expiry
    cache_file.write_bytes(resp.content)
    ct_file.write_text(content_type)

    return Response(
        content=resp.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=2592000"},  # 30 days
    )
