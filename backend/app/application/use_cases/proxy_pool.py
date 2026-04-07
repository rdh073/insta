"""Proxy pool use case — import, classify, persist, and serve working proxies."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field

from app.application.ports.proxy_checker import ProxyCheckerPort
from app.application.ports.proxy_repository import ProxyRepositoryPort
from app.domain.proxy import Proxy, ProxyAnonymity, ProxyProtocol


@dataclass
class RecheckSummary:
    total:   int = 0
    alive:   int = 0
    removed: int = 0


@dataclass
class ImportSummary:
    total:               int = 0
    saved:               int = 0
    skipped_transparent: int = 0
    skipped_duplicate:   int = 0
    skipped_existing:    int = 0
    failed:              int = 0
    errors:              list[str] = field(default_factory=list)


@dataclass
class ProxyDTO:
    host:       str
    port:       int
    protocol:   str
    anonymity:  str
    latency_ms: float
    url:        str


class ProxyPoolUseCases:
    """Orchestrates the proxy lifecycle: import → check → filter → persist → serve."""

    def __init__(
        self,
        checker:    ProxyCheckerPort,
        repo:       ProxyRepositoryPort,
        parser,                          # ProxyParser — injected to keep use case testable
        concurrency: int = 20,
        check_timeout: float = 5.0,
    ):
        self._checker     = checker
        self._repo        = repo
        self._parser      = parser
        self._concurrency = concurrency
        self._timeout     = check_timeout

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    async def import_from_text(self, text: str) -> ImportSummary:
        """Parse proxy lines, check each concurrently, persist eligible ones.

        Duplicates within the batch (same host:port) are counted once and skipped.
        Proxies already present in the repository are skipped without re-checking.
        """
        summary = ImportSummary()
        raws = self._parser.parse_lines(text)
        summary.total = len(raws)

        if not raws:
            return summary

        # ── 1. Deduplicate within this batch (keep first occurrence) ────────
        seen: set[tuple[str, int]] = set()
        unique_raws = []
        for raw in raws:
            key = (raw.host, raw.port)
            if key in seen:
                summary.skipped_duplicate += 1
            else:
                seen.add(key)
                unique_raws.append(raw)

        # ── 2. Skip proxies already stored in the repository ────────────────
        # repo.exists() is synchronous (SQLAlchemy); run in a thread so we
        # don't block the event loop while iterating over a large batch.
        to_check = []
        for raw in unique_raws:
            exists = await asyncio.to_thread(self._repo.exists, raw.host, raw.port)
            if exists:
                summary.skipped_existing += 1
            else:
                to_check.append(raw)

        if not to_check:
            return summary

        # ── 3. Fetch real IP once and share it across all concurrent checks ─
        # Avoids N redundant round-trips to the IP-echo service.
        real_ip: str | None = await self._checker.get_real_ip(self._timeout)

        sem = asyncio.Semaphore(self._concurrency)

        async def check_one(raw):
            url = self._build_url(raw)
            async with sem:
                return await self._checker.check(url, timeout=self._timeout, real_ip=real_ip)

        results = await asyncio.gather(
            *[check_one(r) for r in to_check],
            return_exceptions=True,
        )

        for raw, result in zip(to_check, results):
            if isinstance(result, Exception):
                summary.failed += 1
                summary.errors.append(f"{raw.host}:{raw.port} — {result}")
                continue

            if not result.reachable:
                summary.failed += 1
                if result.error:
                    summary.errors.append(f"{raw.host}:{raw.port} — {result.error}")
                continue

            try:
                proxy = Proxy(
                    host=raw.host,
                    port=raw.port,
                    protocol=ProxyProtocol(result.protocol or "http"),
                    anonymity=ProxyAnonymity(result.anonymity or "transparent"),
                    latency_ms=result.latency_ms or 0.0,
                )
            except ValueError:
                # Unknown protocol or anonymity value — treat as failed
                summary.failed += 1
                continue

            if proxy.is_storable():
                # repo.save() is synchronous; run in a thread to avoid
                # blocking the event loop on every persist.
                await asyncio.to_thread(self._repo.save, proxy)
                summary.saved += 1
            else:
                summary.skipped_transparent += 1

        return summary

    # ------------------------------------------------------------------
    # Recheck
    # ------------------------------------------------------------------

    async def recheck_pool(self) -> RecheckSummary:
        """Re-check all stored proxies concurrently.

        Alive proxies have their latency updated in-place.
        Dead proxies are removed from the pool.
        """
        proxies = await asyncio.to_thread(self._repo.list_all)
        summary = RecheckSummary(total=len(proxies))
        if not proxies:
            return summary

        real_ip: str | None = await self._checker.get_real_ip(self._timeout)
        sem = asyncio.Semaphore(self._concurrency)

        async def check_one(proxy):
            async with sem:
                return await self._checker.check(proxy.url, timeout=self._timeout, real_ip=real_ip)

        results = await asyncio.gather(
            *[check_one(p) for p in proxies],
            return_exceptions=True,
        )

        for proxy, result in zip(proxies, results):
            if isinstance(result, Exception) or not result.reachable:
                await asyncio.to_thread(self._repo.delete, proxy.host, proxy.port)
                summary.removed += 1
            else:
                updated = Proxy(
                    host=proxy.host,
                    port=proxy.port,
                    protocol=proxy.protocol,
                    anonymity=proxy.anonymity,
                    latency_ms=result.latency_ms or 0.0,
                )
                await asyncio.to_thread(self._repo.save, updated)
                summary.alive += 1

        return summary

    # ------------------------------------------------------------------
    # Query / manage
    # ------------------------------------------------------------------

    def list_proxies(self) -> list[ProxyDTO]:
        return [self._to_dto(p) for p in self._repo.list_all()]

    def delete_proxy(self, host: str, port: int) -> None:
        self._repo.delete(host, port)

    def pick_proxy(self) -> str | None:
        """Return a random proxy URL from the pool, or None if pool is empty."""
        proxies = self._repo.list_all()
        if not proxies:
            return None
        return random.choice(proxies).url

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_url(raw) -> str:
        if raw.hint_protocol:
            return f"{raw.hint_protocol}://{raw.host}:{raw.port}"
        return f"{raw.host}:{raw.port}"  # bare — adapter will probe

    @staticmethod
    def _to_dto(proxy: Proxy) -> ProxyDTO:
        return ProxyDTO(
            host=proxy.host,
            port=proxy.port,
            protocol=proxy.protocol.value,
            anonymity=proxy.anonymity.value,
            latency_ms=proxy.latency_ms,
            url=proxy.url,
        )
