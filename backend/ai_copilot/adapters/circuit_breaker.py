"""Circuit breaker for adapter failure protection.

Infrastructure concern — wraps port adapters to prevent cascading failures
when external services (Instagram API, account service) are repeatedly down.

States:
    CLOSED  — normal operation, calls pass through
    OPEN    — fast-fail, calls rejected immediately with CircuitOpenError
    HALF_OPEN — testing recovery, one call allowed through

Transition rules:
    CLOSED → OPEN:     failure_count >= failure_threshold
    OPEN → HALF_OPEN:  recovery_timeout elapsed since last failure
    HALF_OPEN → CLOSED: probe call succeeds
    HALF_OPEN → OPEN:   probe call fails

Usage at composition root (bootstrap):
    breaker = CircuitBreaker("account_context", failure_threshold=3, recovery_timeout=60.0)
    protected = CircuitProtectedProxy(real_adapter, breaker)
    # pass `protected` wherever the port is expected

Dependencies point inward: this module knows nothing about ports, nodes,
or business rules. It only wraps async callables.
"""

from __future__ import annotations

import asyncio
import enum
import functools
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""

    def __init__(self, name: str, remaining_seconds: float):
        self.name = name
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit '{name}' is OPEN — fast-failing for {remaining_seconds:.1f}s more"
        )


class CircuitBreaker:
    """Async-aware circuit breaker state machine.

    Thread-safe for single-event-loop use (standard asyncio).
    """

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    async def call(self, fn, *args, **kwargs) -> Any:
        """Execute fn through the circuit breaker.

        Raises CircuitOpenError if the circuit is open.
        """
        current = self.state

        if current == CircuitState.OPEN:
            remaining = self.recovery_timeout - (time.monotonic() - self._last_failure_time)
            logger.warning(
                "Circuit %r OPEN — rejecting call to %s (%.1fs remaining)",
                self.name, getattr(fn, "__qualname__", fn), remaining,
            )
            raise CircuitOpenError(self.name, max(remaining, 0.0))

        if current == CircuitState.HALF_OPEN:
            if self._half_open_lock.locked():
                remaining = self.recovery_timeout - (time.monotonic() - self._last_failure_time)
                raise CircuitOpenError(self.name, max(remaining, 0.0))
            async with self._half_open_lock:
                return await self._probe(fn, *args, **kwargs)

        # CLOSED — normal path
        return await self._guarded_call(fn, *args, **kwargs)

    async def _guarded_call(self, fn, *args, **kwargs) -> Any:
        try:
            result = await fn(*args, **kwargs)
            async with self._state_lock:
                self._on_success()
            return result
        except CircuitOpenError:
            raise
        except Exception:
            async with self._state_lock:
                self._on_failure()
            raise

    async def _probe(self, fn, *args, **kwargs) -> Any:
        """HALF_OPEN probe: one call decides the circuit's fate."""
        try:
            result = await fn(*args, **kwargs)
            async with self._state_lock:
                self._reset()
            logger.info("Circuit %r probe succeeded — now CLOSED", self.name)
            return result
        except CircuitOpenError:
            raise
        except Exception:
            async with self._state_lock:
                self._trip()
            logger.warning("Circuit %r probe failed — back to OPEN", self.name)
            raise

    def _on_success(self) -> None:
        if self._failure_count > 0:
            self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._trip()

    def _trip(self) -> None:
        prev = self._state
        self._state = CircuitState.OPEN
        self._last_failure_time = time.monotonic()
        if prev != CircuitState.OPEN:
            logger.error(
                "Circuit %r tripped OPEN after %d failures (recovery in %.0fs)",
                self.name, self._failure_count, self.recovery_timeout,
            )

    def _reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def __repr__(self) -> str:
        return f"CircuitBreaker({self.name!r}, state={self.state.value}, failures={self._failure_count})"


class CircuitProtectedProxy:
    """Transparent proxy that routes async method calls through a CircuitBreaker.

    Preserves the adapter's interface so nodes/use cases are unaware of protection.
    Sync methods and properties pass through unchanged.

    Usage:
        real = AccountContextAdapter(...)
        proxy = CircuitProtectedProxy(real, breaker)
        # proxy.get_account_context(...) goes through breaker
        # proxy.some_sync_attr passes through directly
    """

    def __init__(self, delegate: Any, breaker: CircuitBreaker):
        self._delegate = delegate
        self._breaker = breaker

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._delegate, name)
        if asyncio.iscoroutinefunction(attr):
            @functools.wraps(attr)
            async def _protected(*args, **kwargs):
                return await self._breaker.call(attr, *args, **kwargs)
            return _protected
        return attr

    def __repr__(self) -> str:
        return f"CircuitProtectedProxy({self._delegate!r}, {self._breaker!r})"
