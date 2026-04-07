"""AccountSignalAdapter — wraps AccountUseCases to satisfy AccountSignalPort."""

from __future__ import annotations

import asyncio

from ai_copilot.application.risk_control.ports import AccountSignalPort


class AccountSignalAdapter(AccountSignalPort):
    def __init__(self, account_usecases, logs_usecases=None):
        self._account = account_usecases
        self._logs = logs_usecases

    def _resolve_account_id(self, account_id: str) -> str | None:
        """Resolve account_id which may be a username or a UUID.

        Tries username lookup first; if that returns nothing, assumes it's
        already a UUID and verifies it exists in the account list.
        """
        # Try to resolve as username
        try:
            resolved = self._account.find_by_username(account_id)
            if resolved:
                return resolved
        except Exception:
            pass

        # Check if it's a valid direct account_id
        try:
            accounts = self._account.list_accounts()
            if any(a.id == account_id for a in accounts):
                return account_id
        except Exception:
            pass

        return None

    async def get_account_status(self, account_id: str) -> dict:
        try:
            resolved_id = await asyncio.to_thread(self._resolve_account_id, account_id)
            if not resolved_id:
                return {}

            accounts = await asyncio.to_thread(self._account.list_accounts)
            account = next((a for a in accounts if a.id == resolved_id), None)
            if not account:
                return {}

            return {
                "status": account.status,
                "login_state": "logged_in" if account.status == "active" else "not_logged_in",
                "cooldown_until": None,
                "proxy": account.proxy,
                "error_flags": [account.status] if account.status in ("challenge", "2fa_required", "error") else [],
            }
        except Exception:
            return {}

    async def get_recent_events(self, account_id: str, limit: int = 20) -> list[dict]:
        if not self._logs:
            return []
        try:
            # Resolve to username for log lookup
            resolved_id = await asyncio.to_thread(self._resolve_account_id, account_id)
            if not resolved_id:
                return []

            accounts = await asyncio.to_thread(self._account.list_accounts)
            account = next((a for a in accounts if a.id == resolved_id), None)
            username = account.username if account else account_id

            result = await asyncio.to_thread(
                self._logs.read_log_entries,
                username=username,
                limit=limit,
            )
            entries = result.get("entries", []) if isinstance(result, dict) else []
            return [
                {
                    "event_type": entry.get("event", entry.get("event_type", "unknown")),
                    "timestamp": entry.get("ts") or entry.get("timestamp"),
                    "detail": entry.get("detail", ""),
                }
                for entry in entries
            ]
        except Exception:
            return []
