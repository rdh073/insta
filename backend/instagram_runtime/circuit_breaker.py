from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)


class SyncCircuitBreaker:
    """Thread-safe circuit breaker for synchronous (threaded) Instagram uploads.

    Only *retryable* failures (rate limits, transient API errors, timeouts) advance
    the failure counter. Terminal per-account errors (BadPassword, ChallengeRequired)
    do NOT trip the circuit — they are account-level problems, not API degradation.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 120.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    return self.HALF_OPEN
            return self._state

    def allow_request(self) -> bool:
        """True when the circuit is CLOSED or entering HALF_OPEN probe."""
        return self.state != self.OPEN

    def record_success(self) -> None:
        with self._lock:
            was_recovering = self._state == self.OPEN
            self._failure_count = 0
            self._state = self.CLOSED
        if was_recovering:
            logger.info("Circuit %r recovered — CLOSED", self.name)

    def record_failure(self, *, retryable: bool) -> None:
        """Record a failure; only retryable failures progress toward tripping."""
        if not retryable:
            return
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold and self._state != self.OPEN:
                self._state = self.OPEN
                logger.error(
                    "Circuit %r tripped OPEN after %d retryable failures "
                    "(auto-recovery in %.0fs)",
                    self.name,
                    self._failure_count,
                    self.recovery_timeout,
                )

    def __repr__(self) -> str:
        return (
            f"SyncCircuitBreaker({self.name!r}, "
            f"state={self.state}, failures={self._failure_count})"
        )


# Module-level breaker shared across all jobs in this process.
# Opens after 5 consecutive retryable failures to stop hammering Instagram
# when its API is degraded. Recovers automatically after 120 s.
_upload_circuit_breaker = SyncCircuitBreaker(
    "instagram_upload",
    failure_threshold=5,
    recovery_timeout=120.0,
)

