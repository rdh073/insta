"""Proxy repository port — abstract contract for proxy pool persistence."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.proxy import Proxy


@runtime_checkable
class ProxyRepositoryPort(Protocol):
    """Persist and retrieve working, classified proxies."""

    def save(self, proxy: Proxy) -> None:
        """Upsert a proxy entry (keyed on host+port)."""
        ...

    def list_all(self) -> list[Proxy]:
        """Return all stored proxies ordered by latency ascending."""
        ...

    def delete(self, host: str, port: int) -> None:
        """Remove a proxy; no-op if not found."""
        ...

    def exists(self, host: str, port: int) -> bool:
        """Return True if a proxy with this host:port is already stored."""
        ...
