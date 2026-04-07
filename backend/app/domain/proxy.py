"""Proxy domain model — protocol classification, anonymity level, and filter rule."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProxyProtocol(str, Enum):
    HTTP   = "http"
    HTTPS  = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class ProxyAnonymity(str, Enum):
    TRANSPARENT = "transparent"  # server sees real IP or proxy-revealing headers
    ELITE       = "elite"        # server sees only proxy IP, no proxy headers


@dataclass(frozen=True)
class Proxy:
    """Value object representing a checked, classified proxy."""

    host:       str
    port:       int
    protocol:   ProxyProtocol
    anonymity:  ProxyAnonymity
    latency_ms: float

    @property
    def url(self) -> str:
        return f"{self.protocol.value}://{self.host}:{self.port}"

    def is_storable(self) -> bool:
        """Persistence filter: only elite-anonymity proxies enter the pool.

        Transparent proxies reveal the real IP to the target server and are
        useless for account automation — they must never be persisted.
        """
        return self.anonymity == ProxyAnonymity.ELITE
