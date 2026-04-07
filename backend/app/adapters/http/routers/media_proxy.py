"""Image proxy endpoint — bypasses CORP restrictions on Instagram CDN URLs."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

router = APIRouter(prefix="/api/proxy", tags=["proxy"])

_ALLOWED_HOSTS = {
    "instagram.fsrg2-1.fna.fbcdn.net",
    "scontent.cdninstagram.com",
    "instagram.com",
    "cdninstagram.com",
}

_CLIENT = httpx.Client(
    timeout=10,
    headers={"User-Agent": "Mozilla/5.0"},
    follow_redirects=True,
)


@router.get("/image")
def proxy_image(url: str = Query(...)):
    """Proxy an Instagram CDN image to avoid CORP browser blocks."""
    from urllib.parse import urlparse

    host = urlparse(url).netloc
    if not any(host == h or host.endswith("." + h) for h in _ALLOWED_HOSTS):
        raise HTTPException(status_code=400, detail="URL not allowed")

    try:
        resp = _CLIENT.get(url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    content_type = resp.headers.get("content-type", "image/jpeg")
    return Response(
        content=resp.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
