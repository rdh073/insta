"""RecoveryExecutorAdapter — wraps AccountUseCases for relogin and proxy swap."""

from __future__ import annotations

import asyncio

from ai_copilot.application.account_recovery.ports import RecoveryExecutorPort


class RecoveryExecutorAdapter(RecoveryExecutorPort):
    def __init__(self, account_usecases):
        self._account = account_usecases

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

    async def relogin(self, account_id: str, two_fa_code: str | None = None) -> dict:
        try:
            resolved_id = await asyncio.to_thread(self._resolve_account_id, account_id)
            if not resolved_id:
                return {"success": False, "requires_2fa": False, "error": f"Account not found: {account_id}"}

            result = await asyncio.to_thread(self._account.relogin_account, resolved_id)
            # relogin_account returns AccountResponse (a dataclass)
            status = result.status if hasattr(result, "status") else (result.get("status") if isinstance(result, dict) else "unknown")
            success = status == "active"
            return {"success": success, "requires_2fa": status == "2fa_required", "error": None if success else f"status: {status}"}
        except Exception as exc:
            msg = str(exc).lower()
            requires_2fa = "2fa" in msg or "two-factor" in msg or "verification" in msg
            return {"success": False, "requires_2fa": requires_2fa, "error": str(exc)[:120]}

    async def swap_proxy(self, account_id: str, new_proxy: str) -> dict:
        try:
            resolved_id = await asyncio.to_thread(self._resolve_account_id, account_id)
            if not resolved_id:
                return {"success": False, "proxy": new_proxy, "error": f"Account not found: {account_id}"}

            await asyncio.to_thread(self._account.set_account_proxy, resolved_id, new_proxy)
            return {"success": True, "proxy": new_proxy, "error": None}
        except Exception as exc:
            return {"success": False, "proxy": new_proxy, "error": str(exc)[:120]}

    async def get_available_proxy(self, account_id: str) -> str | None:
        # AccountUseCases doesn't manage proxy pools — proxy selection not available here
        return None
