"""Tests for circuit breaker — state transitions, fast-fail, recovery, proxy delegation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import asyncio
import time

import pytest

from ai_copilot.adapters.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitProtectedProxy,
    CircuitState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Counter:
    """Tracks call counts for test assertions."""
    def __init__(self):
        self.calls = 0

    async def succeed(self, *args, **kwargs):
        self.calls += 1
        return "ok"

    async def fail(self, *args, **kwargs):
        self.calls += 1
        raise RuntimeError("boom")


class _FakeAdapter:
    """Fake port adapter with async and sync methods."""
    def __init__(self, *, should_fail: bool = False):
        self.call_count = 0
        self.should_fail = should_fail

    async def do_async(self, value: str) -> str:
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("adapter error")
        return f"result:{value}"

    def do_sync(self) -> str:
        return "sync_ok"

    @property
    def name(self) -> str:
        return "fake"


# ---------------------------------------------------------------------------
# CircuitBreaker state machine
# ---------------------------------------------------------------------------

class TestCircuitBreakerStates:
    @pytest.mark.asyncio
    async def test_starts_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=1.0)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_stays_closed_on_success(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        counter = _Counter()
        for _ in range(10):
            await cb.call(counter.succeed)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert counter.calls == 10

    @pytest.mark.asyncio
    async def test_trips_open_after_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60.0)
        counter = _Counter()
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(counter.fail)
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    @pytest.mark.asyncio
    async def test_rejects_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60.0)
        counter = _Counter()
        with pytest.raises(RuntimeError):
            await cb.call(counter.fail)

        assert cb.state == CircuitState.OPEN

        # Subsequent calls should be rejected immediately
        with pytest.raises(CircuitOpenError) as exc_info:
            await cb.call(counter.succeed)
        assert "OPEN" in str(exc_info.value)
        # The succeed function was never called
        assert counter.calls == 1

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        counter = _Counter()
        with pytest.raises(RuntimeError):
            await cb.call(counter.fail)
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_probe_success_closes(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        counter = _Counter()

        with pytest.raises(RuntimeError):
            await cb.call(counter.fail)
        await asyncio.sleep(0.15)

        result = await cb.call(counter.succeed)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_probe_failure_reopens(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        counter = _Counter()

        with pytest.raises(RuntimeError):
            await cb.call(counter.fail)
        await asyncio.sleep(0.15)

        with pytest.raises(RuntimeError):
            await cb.call(counter.fail)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_resets_failure_count_on_success(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60.0)
        counter_fail = _Counter()
        counter_ok = _Counter()

        # 2 failures (below threshold)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(counter_fail.fail)
        assert cb.failure_count == 2

        # 1 success resets
        await cb.call(counter_ok.succeed)
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# CircuitProtectedProxy
# ---------------------------------------------------------------------------

class TestCircuitProtectedProxy:
    @pytest.mark.asyncio
    async def test_proxies_async_methods(self):
        adapter = _FakeAdapter()
        breaker = CircuitBreaker("proxy_test", failure_threshold=3)
        proxy = CircuitProtectedProxy(adapter, breaker)

        result = await proxy.do_async("hello")
        assert result == "result:hello"
        assert adapter.call_count == 1

    @pytest.mark.asyncio
    async def test_passes_through_sync_methods(self):
        adapter = _FakeAdapter()
        breaker = CircuitBreaker("proxy_test", failure_threshold=3)
        proxy = CircuitProtectedProxy(adapter, breaker)

        assert proxy.do_sync() == "sync_ok"

    @pytest.mark.asyncio
    async def test_passes_through_properties(self):
        adapter = _FakeAdapter()
        breaker = CircuitBreaker("proxy_test", failure_threshold=3)
        proxy = CircuitProtectedProxy(adapter, breaker)

        assert proxy.name == "fake"

    @pytest.mark.asyncio
    async def test_circuit_opens_through_proxy(self):
        adapter = _FakeAdapter(should_fail=True)
        breaker = CircuitBreaker("proxy_test", failure_threshold=2, recovery_timeout=60.0)
        proxy = CircuitProtectedProxy(adapter, breaker)

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await proxy.do_async("x")

        assert breaker.state == CircuitState.OPEN

        # Next call fast-fails without reaching the adapter
        with pytest.raises(CircuitOpenError):
            await proxy.do_async("y")
        assert adapter.call_count == 2  # not 3

    @pytest.mark.asyncio
    async def test_circuit_open_error_contains_name(self):
        adapter = _FakeAdapter(should_fail=True)
        breaker = CircuitBreaker("my_adapter", failure_threshold=1, recovery_timeout=60.0)
        proxy = CircuitProtectedProxy(adapter, breaker)

        with pytest.raises(RuntimeError):
            await proxy.do_async("x")

        with pytest.raises(CircuitOpenError) as exc_info:
            await proxy.do_async("y")

        assert exc_info.value.name == "my_adapter"
        assert exc_info.value.remaining_seconds > 0

    @pytest.mark.asyncio
    async def test_repr(self):
        adapter = _FakeAdapter()
        breaker = CircuitBreaker("test_repr", failure_threshold=3)
        proxy = CircuitProtectedProxy(adapter, breaker)

        r = repr(proxy)
        assert "CircuitProtectedProxy" in r
        assert "test_repr" in r
