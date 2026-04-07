"""Httpx-based proxy checker adapter — connectivity, protocol probe, anonymity detection."""

from __future__ import annotations

import asyncio
import time

import httpx

from app.application.ports.proxy_checker import ProxyCheckResult

# Returns caller's public IP as plain JSON {"ip": "..."}
_IP_URL = "https://api.ipify.org?format=json"

# Echoes the full request (headers + origin IP) as seen by the server
_ECHO_URL = "https://httpbin.org/get"

# Headers that betray proxy presence
_PROXY_HEADERS = frozenset({
    "x-forwarded-for",
    "via",
    "proxy-connection",
    "x-real-ip",
    "forwarded",
    "x-proxy-id",
    "x-bluecoat-via",
})

# Protocol probe order for bare ip:port (no hint)
_PROBE_ORDER = ["http", "socks5", "https"]


class HttpxProxyCheckerAdapter:
    """Tests proxy connectivity, detects protocol, and classifies anonymity level.

    Anonymity detection:
      elite       — server sees only the proxy exit IP, no proxy-revealing headers
      transparent — server sees real IP or proxy-specific headers are present

    Protocol probe (for bare ip:port with no hint):
      Tries http → socks5 → https in order; uses first that succeeds.

    Timeout budget (default 5 s per attempt):
      real_ip lookup : 5 s
      worst-case probe: 3 protocols × 5 s = 15 s
      total worst case: 20 s  (safely under the 30 s client timeout)
    """

    async def check(
        self,
        proxy_url: str,
        timeout: float = 5.0,
        real_ip: str | None = None,
    ) -> ProxyCheckResult:
        """Test proxy and classify it.  proxy_url may include or omit scheme.

        Pass a pre-fetched *real_ip* to skip the ipify lookup — useful when
        checking many proxies concurrently so the lookup is done only once.
        """
        if real_ip is None:
            real_ip = await self._get_real_ip(timeout)
        return await self._check_with_probe(proxy_url, real_ip, timeout)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def get_real_ip(self, timeout: float) -> str | None:
        return await self._get_real_ip(timeout)

    async def _get_real_ip(self, timeout: float) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(_IP_URL)
                return resp.json().get("ip")
        except Exception:
            return None

    async def _check_with_probe(
        self, proxy_url: str, real_ip: str | None, timeout: float
    ) -> ProxyCheckResult:
        """If the URL has no scheme, probe multiple protocols in order."""
        if "://" in proxy_url:
            return await self._attempt(proxy_url, real_ip, timeout)

        # bare ip:port — probe protocols
        for proto in _PROBE_ORDER:
            candidate = f"{proto}://{proxy_url}"
            result = await self._attempt(candidate, real_ip, timeout)
            if result.reachable:
                return result

        return ProxyCheckResult(
            proxy_url=proxy_url,
            reachable=False,
            error="all protocol probes failed (http, socks5, https)",
        )

    async def _attempt(
        self, proxy_url: str, real_ip: str | None, timeout: float
    ) -> ProxyCheckResult:
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(proxy=proxy_url, timeout=timeout) as client:
                resp = await client.get(_ECHO_URL)
                latency_ms = round((time.perf_counter() - t0) * 1000, 1)
                data = resp.json()

                exit_ip = data.get("origin", "").split(",")[0].strip()
                echoed_headers = {k.lower(): v for k, v in data.get("headers", {}).items()}

                anonymity = self._classify_anonymity(exit_ip, echoed_headers, real_ip)
                protocol  = self._extract_protocol(proxy_url)

                return ProxyCheckResult(
                    proxy_url=proxy_url,
                    reachable=True,
                    latency_ms=latency_ms,
                    ip_address=exit_ip,
                    protocol=protocol,
                    anonymity=anonymity,
                )
        except Exception as exc:
            return ProxyCheckResult(
                proxy_url=proxy_url,
                reachable=False,
                error=str(exc)[:200],
            )

    @staticmethod
    def _classify_anonymity(
        exit_ip: str,
        echoed_headers: dict[str, str],
        real_ip: str | None,
    ) -> str:
        """elite if server sees only proxy IP with no proxy-revealing headers."""
        has_proxy_headers = bool(_PROXY_HEADERS & echoed_headers.keys())
        real_ip_visible = real_ip and real_ip in echoed_headers.get("x-forwarded-for", "")

        if has_proxy_headers or real_ip_visible:
            return "transparent"
        return "elite"

    @staticmethod
    def _extract_protocol(proxy_url: str) -> str:
        if "://" in proxy_url:
            return proxy_url.split("://")[0].lower()
        return "http"
