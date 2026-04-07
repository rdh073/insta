"""Instagram adapter layer - client operations."""

__all__ = ["InstagramClientAdapter"]


def __getattr__(name: str):
    """Lazy import adapters so package import does not require instagrapi."""
    if name == "InstagramClientAdapter":
        from .client import InstagramClientAdapter

        return InstagramClientAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
