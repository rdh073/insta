"""HTTP adapter utilities - shared helpers for all routes.

PHASE B MIGRATION:
- Removed ai_tools imports (legacy AI assistant dependency)
- This module now only provides format_error and format_instagram_failure
- These functions are used by non-AI routes (accounts, dashboard, logs, smart_engagement)
- Legacy AI utility functions (stream_tool_calls, resolve_ai_provider, etc.)
  have been removed as they were dead code (unused by AIChartUseCases)
"""

from __future__ import annotations

import json
import uuid
from typing import Optional


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


# PHASE B MIGRATION: Dead code functions removed
# These functions were not used by any consumer:
# - stream_tool_calls (was used by legacy ai_tools, never called)
# - resolve_ai_provider (was used by legacy ai_tools, never called)
# - build_ai_messages (was used by legacy ai_tools, never called)
# - build_ai_client (was used by legacy ai_tools, never called)
#
# AIChartUseCases implements its own _build_messages and uses AIGateway for client,
# so these were duplicate/dead code from an earlier architecture.
