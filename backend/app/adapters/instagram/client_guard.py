"""Shared Instagram adapter client lookup with rate-limit preflight."""

from __future__ import annotations

from typing import Any

from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.error_utils import check_rate_limit


def get_guarded_client(client_repo: ClientRepository, account_id: str) -> Any:
    """Return an authenticated client after rate-limit preflight.

    Raises:
        InstagramRateLimitError: When the account is currently cooling down.
        ValueError: When no authenticated client exists for the account.
    """
    check_rate_limit(account_id)
    client = client_repo.get(account_id)
    if not client:
        raise ValueError(f"Account {account_id} not found or not authenticated")
    return client
