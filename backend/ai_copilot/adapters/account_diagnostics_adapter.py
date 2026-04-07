"""AccountDiagnosticsAdapter — wraps AccountUseCases to satisfy AccountDiagnosticsPort."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ai_copilot.application.account_recovery.ports import AccountDiagnosticsPort


_CLASSIFIABLE_STATUSES = {
    "challenge": "challenge",
    "2fa_required": "2fa_required",
    "error": "session_expired",
    "idle": "session_expired",
}


class AccountDiagnosticsAdapter(AccountDiagnosticsPort):
    def __init__(self, account_usecases: Any, connectivity_usecases: Any = None):
        self._account = account_usecases
        self._connectivity = connectivity_usecases

    def _resolve_account_id(self, account_id: str) -> str | None:
        """Resolve account_id which may be a username or a UUID."""
        try:
            resolved = self._account.find_by_username(account_id)
            if resolved:
                return resolved
        except Exception:
            pass
        try:
            accounts = self._account.list_accounts()
            if any(a.id == account_id for a in accounts):
                return account_id
        except Exception:
            pass
        return None

    def _find_account(self, resolved_id: str):
        """Return the AccountResponse for a resolved account_id, or None."""
        try:
            accounts = self._account.list_accounts()
            return next((a for a in accounts if a.id == resolved_id), None)
        except Exception:
            return None

    async def read_error_state(self, account_id: str) -> dict:
        try:
            resolved_id = await asyncio.to_thread(self._resolve_account_id, account_id)
            if not resolved_id:
                return {
                    "has_error": True,
                    "error_message": f"Account not found: {account_id}",
                }

            account = await asyncio.to_thread(self._find_account, resolved_id)
            if not account:
                return {
                    "has_error": True,
                    "error_message": f"Account not found: {account_id}",
                }

            status = account.status
            has_error = status not in ("active",)
            login_state = "logged_in" if status == "active" else status
            return {
                "has_error": has_error,
                "login_state": login_state,
                "status": status,
                "proxy": account.proxy,
                "error_message": "" if not has_error else f"Account status: {status}",
                "_resolved_id": resolved_id,
            }
        except Exception as exc:
            return {"has_error": True, "error_message": str(exc)[:120]}

    async def classify_issue(self, error_state: dict) -> str:
        if not error_state.get("has_error"):
            return "none"

        login_state = error_state.get("login_state", "")
        status = error_state.get("status", "")
        msg = (error_state.get("error_message") or "").lower()

        # Map directly from status (most reliable source)
        if status in _CLASSIFIABLE_STATUSES:
            return _CLASSIFIABLE_STATUSES[status]

        # Fall back to login_state string matching
        if "challenge" in login_state or "challenge" in msg:
            return "challenge"
        if "block" in msg:
            return "blocked"
        if "2fa" in login_state or "2fa" in msg or "two-factor" in msg:
            return "2fa_required"
        if "session" in msg or "expired" in msg:
            return "session_expired"

        return "unknown"

    async def verify_account_health(self, account_id: str) -> dict:
        """Check real Instagram connectivity when connectivity_usecases is available.

        If ``connectivity_usecases`` was injected (preferred), this calls
        ``verify_account_connectivity`` which performs a live ``account_info()``
        probe and updates health-tracking fields on the account record.

        Falls back to reading local ``status`` when connectivity_usecases is
        not configured (e.g., legacy wiring or unit tests).
        """
        try:
            resolved_id = await asyncio.to_thread(self._resolve_account_id, account_id)
            if not resolved_id:
                return {
                    "healthy": False,
                    "login_state": "not_found",
                    "checked_at": time.time(),
                }

            # --- Real probe via connectivity use case ---
            if self._connectivity is not None:
                try:
                    result = await asyncio.to_thread(
                        self._connectivity.verify_account_connectivity, resolved_id
                    )
                    healthy = result.status == "active"
                    return {
                        "healthy": healthy,
                        "login_state": "logged_in" if healthy else result.status,
                        "status": result.status,
                        "last_verified_at": result.last_verified_at,
                        "last_error": result.last_error,
                        "last_error_code": result.last_error_code,
                        "checked_at": time.time(),
                    }
                except ValueError:
                    # Account not found or not logged in.
                    return {
                        "healthy": False,
                        "login_state": "not_found",
                        "checked_at": time.time(),
                    }

            # --- Fallback: local status read only ---
            account = await asyncio.to_thread(self._find_account, resolved_id)
            if not account:
                return {
                    "healthy": False,
                    "login_state": "not_found",
                    "checked_at": time.time(),
                }

            healthy = account.status == "active"
            return {
                "healthy": healthy,
                "login_state": "logged_in" if healthy else account.status,
                "status": account.status,
                "checked_at": time.time(),
            }
        except Exception:
            return {"healthy": False, "login_state": "error", "checked_at": time.time()}
