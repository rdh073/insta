"""ProxyRotationAdapter — wraps AccountUseCases for proxy operations."""

from __future__ import annotations

import asyncio
import time

from ai_copilot.application.risk_control.ports import ProxyRotationPort


class ProxyRotationAdapter(ProxyRotationPort):
    def __init__(self, account_usecases):
        self._account = account_usecases

    async def get_candidate_proxy(self, account_id: str) -> str | None:
        try:
            result = await asyncio.to_thread(
                self._account.get_available_proxy,
                account_id=account_id,
            )
            return result if isinstance(result, str) else None
        except Exception:
            return None

    async def apply_proxy(self, account_id: str, proxy: str) -> dict:
        try:
            await asyncio.to_thread(
                self._account.set_account_proxy,
                account_id=account_id,
                proxy=proxy,
            )
            return {"success": True, "proxy": proxy, "applied_at": time.time()}
        except Exception as exc:
            return {"success": False, "proxy": proxy, "error": str(exc)[:80]}
