"""Bootstrap module public exports with minimal import side effects."""

from __future__ import annotations


def __getattr__(name: str):
    """Resolve container wiring lazily for package-level imports."""
    if name == "create_services":
        from .container import create_services as _create_services

        return _create_services
    raise AttributeError(name)


__all__ = ["create_services"]
