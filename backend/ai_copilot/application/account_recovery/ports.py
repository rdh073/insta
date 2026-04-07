"""Ports for Account Recovery workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod


class AccountDiagnosticsPort(ABC):
    @abstractmethod
    async def read_error_state(self, account_id: str) -> dict:
        """Return current error state: {has_error, error_type, error_message, login_state, proxy}."""

    @abstractmethod
    async def classify_issue(self, error_state: dict) -> str:
        """Classify error into: 'challenge'|'blocked'|'session_expired'|'2fa_required'|'unknown'|'none'."""

    @abstractmethod
    async def verify_account_health(self, account_id: str) -> dict:
        """Return health check: {healthy, login_state, status, checked_at}."""


class RecoveryExecutorPort(ABC):
    @abstractmethod
    async def relogin(self, account_id: str, two_fa_code: str | None = None) -> dict:
        """Attempt relogin. Returns {success, requires_2fa, error}."""

    @abstractmethod
    async def swap_proxy(self, account_id: str, new_proxy: str) -> dict:
        """Swap account proxy. Returns {success, proxy, error}."""

    @abstractmethod
    async def get_available_proxy(self, account_id: str) -> str | None:
        """Return an available proxy string, or None."""
