"""App-owned persistence adapter exceptions."""

from __future__ import annotations


class PersistenceInfrastructureError(RuntimeError):
    """Stable infrastructure-level failure for persistence adapters."""

