"""SSE token issuance endpoint.

POST /api/sse/token

Protected by the normal X-API-Key middleware.  Returns a short-lived reusable token
that EventSource consumers can pass as ?sse_token= instead of the raw API
key, preventing the key from appearing in server access logs.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/sse", tags=["sse"])


@router.post("/token", summary="Issue a short-lived reusable SSE token")
async def issue_sse_token(request: Request) -> dict:
    """Return a short-lived token for ?sse_token= on SSE endpoints.

    Runtime contract:
    - Token is reusable until expiry (not consumed on use).
    - TTL comes from store.TTL_SECONDS (currently 300 seconds).
    - Middleware validates token existence + expiry and rejects invalid/expired tokens.
    """
    store = getattr(request.app.state, "sse_token_store", None)
    if store is None:
        # API key auth not configured — SSE token not needed, return empty sentinel
        return {"token": "", "expires_in": 0, "required": False}

    token = store.issue()
    return {"token": token, "expires_in": store.TTL_SECONDS, "required": True}
