"""Proxy line parser — supports three input formats.

Accepted formats
----------------
  ip:port              bare address, protocol unknown (probed during check)
  proto:ip:port        shorthand without "://"
  proto://ip:port      standard URL form

Supported protocol tokens: http, https, socks, socks4, socks5
"socks" is normalised to "socks5".
"""

from __future__ import annotations

from dataclasses import dataclass


_KNOWN_PROTOS = {"http", "https", "socks", "socks4", "socks5"}


@dataclass(frozen=True)
class RawProxy:
    """Parsed proxy entry before connectivity check."""

    host:          str
    port:          int
    hint_protocol: str | None  # None → probe during check (http → socks5 → https)


class ProxyParser:
    """Parses a block of text into a list of RawProxy entries.

    Lines starting with '#' and blank lines are silently skipped.
    Malformed lines are silently skipped (no exception raised).
    """

    def parse_lines(self, text: str) -> list[RawProxy]:
        result: list[RawProxy] = []
        for line in text.splitlines():
            line = line.strip()
            raw = self._parse_line(line)
            if raw is not None:
                result.append(raw)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_line(self, line: str) -> RawProxy | None:
        if not line or line.startswith("#"):
            return None

        try:
            # ── proto://ip:port ────────────────────────────────────────
            if "://" in line:
                scheme, rest = line.split("://", 1)
                scheme = scheme.lower()
                if scheme not in _KNOWN_PROTOS:
                    return None
                host, port = self._split_host_port(rest)
                return RawProxy(host, port, self._normalize_proto(scheme))

            parts = line.split(":")
            if len(parts) == 2:
                # ── ip:port ────────────────────────────────────────────
                host, port = parts[0].strip(), int(parts[1].strip())
                return RawProxy(host, port, None)

            if len(parts) == 3:
                # ── proto:ip:port ──────────────────────────────────────
                scheme = parts[0].strip().lower()
                if scheme not in _KNOWN_PROTOS:
                    return None
                host, port = parts[1].strip(), int(parts[2].strip())
                return RawProxy(host, port, self._normalize_proto(scheme))

        except (ValueError, AttributeError):
            pass  # malformed line

        return None

    @staticmethod
    def _split_host_port(s: str) -> tuple[str, int]:
        host, port_str = s.rsplit(":", 1)
        return host.strip(), int(port_str.strip())

    @staticmethod
    def _normalize_proto(s: str) -> str:
        return "socks5" if s == "socks" else s
