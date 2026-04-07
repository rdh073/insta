"""Proxy pool management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.adapters.http.dependencies import get_proxy_pool_usecases

router = APIRouter(prefix="/api/proxies", tags=["proxies"])


# ── Request schemas ──────────────────────────────────────────────────────────

class ImportProxiesRequest(BaseModel):
    text: str


class CheckProxyRequest(BaseModel):
    url: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/import")
async def import_proxies(body: ImportProxiesRequest, usecases=Depends(get_proxy_pool_usecases)):
    """Parse a text blob of proxy lines, check each, and persist elite ones."""
    summary = await usecases.import_from_text(body.text)
    return {
        "total":               summary.total,
        "saved":               summary.saved,
        "skipped_transparent": summary.skipped_transparent,
        "skipped_duplicate":   summary.skipped_duplicate,
        "skipped_existing":    summary.skipped_existing,
        "failed":              summary.failed,
        "errors":              summary.errors[:20],
    }


@router.get("")
def list_proxies(usecases=Depends(get_proxy_pool_usecases)):
    """List all stored proxies ordered by latency."""
    return [
        {
            "host":      p.host,
            "port":      p.port,
            "protocol":  p.protocol,
            "anonymity": p.anonymity,
            "latencyMs": p.latency_ms,
            "url":       p.url,
        }
        for p in usecases.list_proxies()
    ]


@router.delete("/{host}/{port}", status_code=204)
def delete_proxy(host: str, port: int, usecases=Depends(get_proxy_pool_usecases)):
    """Remove a proxy from the pool."""
    usecases.delete_proxy(host, port)


@router.post("/recheck")
async def recheck_pool(usecases=Depends(get_proxy_pool_usecases)):
    """Re-check all stored proxies concurrently; remove dead ones and update latency."""
    summary = await usecases.recheck_pool()
    return {
        "total":   summary.total,
        "alive":   summary.alive,
        "removed": summary.removed,
    }


@router.post("/check")
async def check_proxy(body: CheckProxyRequest, usecases=Depends(get_proxy_pool_usecases)):
    """Test a single proxy URL (does not persist the result)."""
    checker = usecases._checker
    result = await checker.check(body.url)
    return {
        "proxyUrl":  result.proxy_url,
        "reachable": result.reachable,
        "latencyMs": result.latency_ms,
        "ipAddress": result.ip_address,
        "protocol":  result.protocol,
        "anonymity": result.anonymity,
        "error":     result.error,
    }
