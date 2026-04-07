"""Ports for Risk Control workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod


class AccountSignalPort(ABC):
    @abstractmethod
    async def get_account_status(self, account_id: str) -> dict:
        """Return account status dict: {status, login_state, cooldown_until, proxy, error_flags}."""

    @abstractmethod
    async def get_recent_events(self, account_id: str, limit: int = 20) -> list[dict]:
        """Return recent activity events: [{event_type, timestamp, detail}]."""


class PolicyDecisionPort(ABC):
    @abstractmethod
    async def evaluate(
        self,
        account_id: str,
        risk_level: str,
        risk_factors: list[str],
        recent_events: list[dict],
    ) -> str:
        """Return policy decision: 'continue'|'cooldown'|'rotate_proxy'|'escalate'."""

    @abstractmethod
    async def apply_cooldown(self, account_id: str, duration_seconds: float) -> float:
        """Apply cooldown to account. Returns cooldown_until timestamp."""


class ProxyRotationPort(ABC):
    @abstractmethod
    async def get_candidate_proxy(self, account_id: str) -> str | None:
        """Return a candidate proxy string, or None if none available."""

    @abstractmethod
    async def apply_proxy(self, account_id: str, proxy: str) -> dict:
        """Apply proxy to account. Returns {success, proxy, applied_at}."""
