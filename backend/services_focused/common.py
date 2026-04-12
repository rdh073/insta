from __future__ import annotations

import datetime

from app.adapters.instagram.exception_handler import instagram_exception_handler


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def utc_now_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def classify_exception(
    error: Exception,
    *,
    operation: str,
    account_id: str | None = None,
    username: str | None = None,
):
    """Translate an exception to the shared Instagram failure contract."""
    return instagram_exception_handler.handle(
        error,
        operation=operation,
        account_id=account_id,
        username=username,
    )

