"""Proxy pool tools for AI registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .core import ToolRegistry, schema

if TYPE_CHECKING:
    from .builder import ToolBuilderContext


def register_proxy_pool_tools(registry: ToolRegistry, context: "ToolBuilderContext") -> None:
    """Register proxy pool management tools."""

    def _proxy_to_dict(proxy) -> dict:
        return {
            "host": proxy.host,
            "port": proxy.port,
            "protocol": proxy.protocol,
            "anonymity": proxy.anonymity,
            "latency_ms": proxy.latency_ms,
            "url": proxy.url,
        }

    def list_proxy_pool_handler(_args: dict) -> dict:
        if context.proxy_pool_usecases is None:
            return {"error": "Proxy pool use cases not available"}
        proxies = context.proxy_pool_usecases.list_proxies()
        return {"count": len(proxies), "proxies": [_proxy_to_dict(p) for p in proxies]}

    async def import_proxies_handler(args: dict) -> dict:
        if context.proxy_pool_usecases is None:
            return {"error": "Proxy pool use cases not available"}
        text = args.get("text", "")
        if not text.strip():
            return {"error": "text is required"}
        summary = await context.proxy_pool_usecases.import_from_text(text)
        return {
            "total": summary.total,
            "saved": summary.saved,
            "skipped_transparent": summary.skipped_transparent,
            "skipped_duplicate": summary.skipped_duplicate,
            "skipped_existing": summary.skipped_existing,
            "failed": summary.failed,
            "errors": summary.errors[:10],
        }

    async def recheck_proxy_pool_handler(_args: dict) -> dict:
        if context.proxy_pool_usecases is None:
            return {"error": "Proxy pool use cases not available"}
        summary = await context.proxy_pool_usecases.recheck_pool()
        return {
            "total": summary.total,
            "alive": summary.alive,
            "removed": summary.removed,
        }

    def delete_proxy_handler(args: dict) -> dict:
        if context.proxy_pool_usecases is None:
            return {"error": "Proxy pool use cases not available"}
        host = args.get("host", "")
        port = args.get("port")
        if not host:
            return {"error": "host is required"}
        if port is None:
            return {"error": "port is required"}
        try:
            context.proxy_pool_usecases.delete_proxy(host, int(port))
            return {"success": True, "deleted": f"{host}:{port}"}
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}

    def pick_proxy_handler(_args: dict) -> dict:
        if context.proxy_pool_usecases is None:
            return {"error": "Proxy pool use cases not available"}
        url = context.proxy_pool_usecases.pick_proxy()
        if url is None:
            return {"proxy_url": None, "message": "No working proxies available in pool"}
        return {"proxy_url": url}

    registry.register(
        "list_proxy_pool",
        list_proxy_pool_handler,
        schema(
            "list_proxy_pool",
            "List all proxies in the proxy pool with their status and latency.",
            properties={},
            required=[],
        ),
    )

    registry.register(
        "import_proxies",
        import_proxies_handler,
        schema(
            "import_proxies",
            "Import proxies from a newline-separated text list. Each line should be a proxy URL (e.g. http://user:pass@host:port).",
            properties={
                "text": {
                    "type": "string",
                    "description": "Newline-separated list of proxy URLs to import",
                },
            },
            required=["text"],
        ),
    )

    registry.register(
        "recheck_proxy_pool",
        recheck_proxy_pool_handler,
        schema(
            "recheck_proxy_pool",
            "Re-test all proxies in the pool. Removes dead proxies and updates latency for alive ones.",
            properties={},
            required=[],
        ),
    )

    registry.register(
        "delete_proxy",
        delete_proxy_handler,
        schema(
            "delete_proxy",
            "Delete a proxy from the pool by host and port.",
            properties={
                "host": {"type": "string", "description": "Proxy host/IP"},
                "port": {"type": "integer", "description": "Proxy port"},
            },
            required=["host", "port"],
        ),
    )

    registry.register(
        "pick_proxy",
        pick_proxy_handler,
        schema(
            "pick_proxy",
            "Pick a random working proxy from the pool.",
            properties={},
            required=[],
        ),
    )
