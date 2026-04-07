"""PolicyDecisionAdapter — pure Python rule engine, no external dependencies."""

from __future__ import annotations

import asyncio
import time

from ai_copilot.application.risk_control.ports import PolicyDecisionPort


class PolicyDecisionAdapter(PolicyDecisionPort):
    """Rule-based policy engine.

    Decision table (in priority order):
    1. risk_level == 'critical'              → escalate
    2. 'login_state:*' in risk_factors       → escalate
    3. 'challenge_flag' in risk_factors      → escalate
    4. risk_level == 'high'                  → cooldown
    5. 'in_cooldown' in risk_factors         → rotate_proxy (try fresh proxy)
    6. risk_level == 'medium'                → cooldown
    7. default                               → continue
    """

    def __init__(self, account_usecases=None):
        self._account = account_usecases

    async def evaluate(
        self,
        account_id: str,
        risk_level: str,
        risk_factors: list[str],
        recent_events: list[dict],
    ) -> str:
        # Critical always escalates
        if risk_level == "critical":
            return "escalate"

        # Login or challenge issues need operator
        if any(f.startswith("login_state:") for f in risk_factors):
            return "escalate"
        if "challenge_flag" in risk_factors:
            return "escalate"

        # High risk → cooldown
        if risk_level == "high":
            return "cooldown"

        # Already in cooldown → try rotating proxy
        if "in_cooldown" in risk_factors:
            return "rotate_proxy"

        # Medium → cooldown
        if risk_level == "medium":
            return "cooldown"

        return "continue"

    async def apply_cooldown(self, account_id: str, duration_seconds: float) -> float:
        cooldown_until = time.time() + duration_seconds
        if self._account is not None:
            try:
                await asyncio.to_thread(
                    self._account.set_account_cooldown,
                    account_id=account_id,
                    cooldown_until=cooldown_until,
                )
            except Exception:
                pass
        return cooldown_until
