"""SSE token issuance endpoint.

POST /api/sse/token

Protected by the normal X-API-Key middleware.  Returns a single-use token
that EventSource consumers can pass as ?sse_token= instead of the raw API
key, preventing the key from appearing in server access logs.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/sse", tags=["sse"])


@router.post("/token", summary="Issue a short-lived one-time SSE token")
async def issue_sse_token(request: Request) -> dict:
    """Return a token valid for 30 s that can be used as ?sse_token= on
    any SSE endpoint.  The token is consumed (deleted) on first use."""
    store = getattr(request.app.state, "sse_token_store", None)
    if store is None:
        # API key auth not configured — SSE token not needed, return empty sentinel
        return {"token": "", "expires_in": 0, "required": False}

    token = store.issue()
    return {"token": token, "expires_in": store.TTL_SECONDS, "required": True}
