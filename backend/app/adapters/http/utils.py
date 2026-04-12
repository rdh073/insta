"""HTTP adapter utilities - shared helpers for all routes.

PHASE B MIGRATION:
- Removed ai_tools imports (legacy AI assistant dependency)
- This module now provides reusable error formatters used by HTTP routers
- Legacy AI utility functions (stream_tool_calls, resolve_ai_provider, etc.)
  have been removed as they were dead code (unused by AIChartUseCases)
"""

from __future__ import annotations

def format_error(error: Exception, context: str = "Error") -> str:
    """Format exceptions into user-facing text without vendor class parsing."""
    failure_payload = format_instagram_failure(error)
    if failure_payload.get("code"):
        return str(failure_payload["detail"])

    error_str = str(error).strip()
    if error_str:
        msg = error_str[:100]
        return f"{context}: {msg}" if context and context != "Error" else msg

    return context if context and context != "Error" else "An error occurred"


def format_instagram_failure(failure) -> dict:
    """
    Format an InstagramFailure into an HTTP-friendly response dict.

    Returns dict with 'status_code' and 'detail' keys.
    """
    from app.domain.instagram_failures import InstagramFailure, InstagramAdapterError

    # Unwrap adapter errors so their inner failure is formatted correctly.
    if isinstance(failure, InstagramAdapterError):
        failure = failure.failure

    if not isinstance(failure, InstagramFailure):
        # Fallback for non-failure exceptions
        return {
            "status_code": 500,
            "detail": str(failure) or "An error occurred",
        }

    return {
        "status_code": failure.http_hint or 400,
        "detail": failure.user_message,
        "code": failure.code,
        "family": failure.family,
    }


def format_instagram_http_error(
    error: Exception,
    *,
    context: str,
    validation_status: int = 400,
    fallback_status: int = 400,
) -> tuple[int, str | dict]:
    """Map an exception from Instagram routes into status + HTTP detail payload.

    Contract:
    - Translated Instagram failures keep their ``http_hint`` and return a
      structured payload: ``{"message", "code", "family"}``.
    - Plain validation/domain ``ValueError`` remains ``validation_status``
      with string detail (historical router contract).
    - Legacy ``InstagramRateLimitError`` is surfaced as HTTP 429.
    """
    from app.adapters.instagram.error_utils import InstagramRateLimitError

    translated_failure = getattr(error, "_instagram_failure", None)
    if translated_failure is not None:
        payload = format_instagram_failure(translated_failure)
        return int(payload["status_code"]), {
            "message": str(payload["detail"]),
            "code": payload.get("code", "unknown_error"),
            "family": payload.get("family", "unknown"),
        }

    payload = format_instagram_failure(error)
    if payload.get("code"):
        return int(payload["status_code"]), {
            "message": str(payload["detail"]),
            "code": payload.get("code", "unknown_error"),
            "family": payload.get("family", "unknown"),
        }

    if isinstance(error, InstagramRateLimitError):
        return 429, format_error(
            error,
            "Rate limited by Instagram. Please wait before trying again.",
        )

    if isinstance(error, ValueError):
        return validation_status, format_error(error, context)

    return fallback_status, format_error(error, context)


# PHASE B MIGRATION: Dead code functions removed
# These functions were not used by any consumer:
# - stream_tool_calls (was used by legacy ai_tools, never called)
# - resolve_ai_provider (was used by legacy ai_tools, never called)
# - build_ai_messages (was used by legacy ai_tools, never called)
# - build_ai_client (was used by legacy ai_tools, never called)
#
# AIChartUseCases implements its own _build_messages and uses AIGateway for client,
# so these were duplicate/dead code from an earlier architecture.
