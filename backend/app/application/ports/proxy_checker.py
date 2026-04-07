"""Proxy checker port — abstract contract for testing proxy reachability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ProxyCheckResult:
    """Result of a proxy connectivity test."""

    proxy_url: str
    reachable: bool
    latency_ms: float | None = None   # round-trip latency through proxy (ms)
    ip_address: str | None = None     # exit IP seen by the test target
    error: str | None = None          # truncated error message on failure
    protocol:  str | None = None      # detected protocol: "http","https","socks4","socks5"
    anonymity: str | None = None      # detected anonymity: "transparent" or "elite"


@runtime_checkable
class ProxyCheckerPort(Protocol):
    """Abstract port for testing proxy connectivity."""

    async def get_real_ip(self, timeout: float = 5.0) -> str | None:
        """Return the caller's public IP address, or None on failure.

        Implementations should suppress network errors and return None so
        callers can still proceed with anonymity classification degraded.
        """
        ...

    async def check(
        self,
        proxy_url: str,
        timeout: float = 5.0,
        real_ip: str | None = None,
    ) -> ProxyCheckResult:
        """Test if a proxy URL is reachable and measure latency.

        Args:
            proxy_url: Proxy URL to test (http://, https://, socks5://).
            timeout: Connection + read timeout in seconds.
            real_ip: Caller's public IP, used for anonymity classification.
                     When provided, avoids a redundant lookup to the IP-echo service.

        Returns:
            ProxyCheckResult with reachable=True and latency_ms on success,
            or reachable=False and error on failure.
        """
        ...
