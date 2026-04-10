"""FastAPI application - thin bootstrap entry point.

ARCHITECTURE:
- This file is NOT responsible for business logic
- It only bootstraps FastAPI and registers routers
- All smart engagement logic is in: ai_copilot/application/
  (graphs, use_cases, nodes, ports, adapters)
- Adapters can delegate to legacy code (instagram.py, services.py)
  but don't own smart engagement decisions
- Never add smart engagement logic directly here
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import logging
import os
import secrets

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters.http.observability import register_observability
from app.adapters.persistence.factory import build_sql_persistence_store, current_persistence_backend
from app.bootstrap.runtime import APP_VERSION, load_runtime_settings


logger = logging.getLogger("instamanager.bootstrap")


def _resolve_oauth_state_secret() -> str:
    """Resolve the secret used to sign short-lived OAuth callback state."""
    return (
        os.environ.get("OAUTH_STATE_SECRET", "").strip()
        or os.environ.get("AUTH_SECRET", "").strip()
        or secrets.token_urlsafe(32)
    )


async def _restore_pending_jobs(job_repo, scheduler) -> None:
    """Re-queue pending/scheduled jobs from persistent storage on startup.

    Required for SQL backends (sqlite/postgres) where the in-memory job store
    (state._jobs) is empty after a restart even though the DB still holds the
    job records.  Calling job_repo.set() for each job triggers the dual-write
    that repopulates state._jobs so PostJobExecutor can find the job by ID.
    """
    try:
        jobs = job_repo.list_all()
    except Exception as exc:
        logger.warning("job_restore.list_failed reason=%s", exc)
        return

    pending = [j for j in jobs if j.status in ("pending", "scheduled")]
    if not pending:
        return

    logger.info("job_restore.start count=%d", len(pending))
    for job in pending:
        try:
            # Dual-write back to in-memory state so PostJobExecutor can find it.
            job_repo.set(job.id, job)
            # Re-enqueue on the scheduler (respects scheduled_at delay).
            scheduler.enqueue(job.id, job.scheduled_at)
            logger.info("job_restore.queued job_id=%s status=%s", job.id, job.status)
        except Exception as exc:
            logger.warning("job_restore.skip job_id=%s reason=%s", job.id, exc)


async def _restore_sessions(account_repo, relogin_fn, hydrate_fn=None) -> None:
    """Background task: relogin all persisted accounts on startup.

    After each successful relogin, fires profile hydration (followers/following)
    so the frontend receives account_updated SSE events without needing to poll.
    """
    ids = account_repo.list_all_ids()
    if not ids:
        return

    logger.info("session_restore.start count=%d", len(ids))

    async def _one(account_id: str) -> None:
        try:
            await asyncio.to_thread(relogin_fn, account_id)
            logger.info("session_restore.ok account_id=%s", account_id)
            if hydrate_fn:
                try:
                    await asyncio.to_thread(hydrate_fn, account_id)
                except Exception as exc:
                    logger.debug("session_restore.hydrate_skipped account_id=%s reason=%s", account_id, exc)
        except Exception as exc:
            logger.warning("session_restore.failed account_id=%s reason=%s", account_id, exc)

    # Sequential with delay — avoids rate-limiting when restoring many accounts.
    for aid in ids:
        await _one(aid)
        await asyncio.sleep(1.5)


def create_app() -> FastAPI:
    """Create the FastAPI application with production-safe runtime defaults."""
    from app.bootstrap.logging_config import configure_vendor_logging
    configure_vendor_logging()

    settings = load_runtime_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from app.adapters.http.dependencies import get_services

        services = get_services()
        app.state.oauth_state_secret = _resolve_oauth_state_secret()

        # Start the post-job dispatch queue.
        job_queue = services["scheduler"]
        if hasattr(job_queue, "start"):
            job_queue.start()

        # Restore pending jobs from persistent storage (no-op for memory backend).
        asyncio.ensure_future(
            _restore_pending_jobs(
                job_repo=services["_job_repo"],
                scheduler=job_queue,
            )
        )

        # Wire event buses to the running event loop for SSE push.
        from app.adapters.scheduler.event_bus import post_job_event_bus
        from app.adapters.http.event_bus import account_event_bus
        from app.adapters.http.log_stream_bus import log_stream_bus
        loop = asyncio.get_running_loop()
        post_job_event_bus.set_loop(loop)
        account_event_bus.set_loop(loop)
        log_stream_bus.set_loop(loop)

        # Re-attach SSE log handler after uvicorn's dictConfig resets logging.
        # Must run inside lifespan so it fires after uvicorn finishes its own
        # logging setup (which would otherwise reset the root logger level).
        from app.bootstrap.logging_config import _attach_sse_handler
        _attach_sse_handler()

        logger.info("InstaManager started — session restore queued")
        from app.adapters.http.routers.accounts import _hydrate_and_publish
        account_auth = services["account_auth"]

        asyncio.ensure_future(
            _restore_sessions(
                account_repo=services["_account_repo"],
                relogin_fn=services["_relogin_fn"],
                hydrate_fn=lambda aid: _hydrate_and_publish(account_auth, aid),
            )
        )
        yield

        # Graceful shutdown.
        if hasattr(job_queue, "shutdown"):
            job_queue.shutdown()

    app = FastAPI(
        title="InstaManager API v2",
        version=APP_VERSION,
        description="Clean architecture backend with domain, application, and adapter layers",
        lifespan=lifespan,
    )
    app.state.runtime_settings = settings
    app.state.persistence_backend = current_persistence_backend()
    app.state.persistence_store = build_sql_persistence_store()

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=list(settings.cors_methods),
            allow_headers=list(settings.cors_headers),
        )

    _api_key = os.environ.get("API_KEY", "").strip()
    if _api_key:
        from app.adapters.http.sse_token import SseTokenStore
        app.state.sse_token_store = SseTokenStore()

        _API_KEY_SKIP = {
            "/health", "/",
            "/docs", "/openapi.json", "/redoc",
            "/api/dashboard/auth/status",
            "/api/dashboard/auth/login",
        }

        @app.middleware("http")
        async def api_key_middleware(request: Request, call_next):
            if request.url.path in _API_KEY_SKIP:
                return await call_next(request)

            # Prefer SSE token (safe for logs) over raw API key in query string.
            # Tokens are reusable within their TTL so EventSource auto-reconnect works.
            sse_token = request.query_params.get("sse_token", "")
            if sse_token:
                store: SseTokenStore = app.state.sse_token_store
                if not store.validate(sse_token):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or expired SSE token"},
                    )
                return await call_next(request)

            # Header first; raw query param kept as last-resort fallback
            key = request.headers.get("X-API-Key", "") or request.query_params.get("x_api_key", "")
            if not secrets.compare_digest(key, _api_key):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key"},
                )
            return await call_next(request)

    from app.adapters.http.rate_limit import load_rate_limit_settings, register_rate_limit
    register_rate_limit(app, load_rate_limit_settings())
    register_observability(app, enable_request_logging=settings.request_logging_enabled)

    # Register routers
    from app.adapters.http.routers.accounts import router as accounts_router
    from app.adapters.http.routers.media_proxy import router as media_proxy_router
    from app.adapters.http.routers.dashboard import router as dashboard_router
    from app.adapters.http.routers.logs import router as logs_router
    from app.adapters.http.routers.posts import router as posts_router
    from app.adapters.http.routers.ai import router as ai_router
    from app.adapters.http.routers.instagram import router as instagram_router
    from app.adapters.http.routers.smart_engagement import router as smart_engagement_router
    from app.adapters.http.routers.llm_config import router as llm_config_router
    from app.adapters.http.routers.proxies import router as proxies_router
    from app.adapters.http.routers.sse import router as sse_router
    from ai_copilot.api import router as ai_copilot_router

    app.include_router(accounts_router)
    app.include_router(media_proxy_router)
    app.include_router(dashboard_router)
    app.include_router(logs_router)
    app.include_router(posts_router)
    app.include_router(instagram_router)
    # Register ai_copilot first so /api/ai/chat/graph resolves to operator copilot
    # instead of the legacy graph-chat adapter route.
    app.include_router(ai_copilot_router)
    app.include_router(ai_router)
    app.include_router(smart_engagement_router)
    app.include_router(llm_config_router)
    app.include_router(proxies_router)
    app.include_router(sse_router)

    @app.get("/health")
    def health_check(request: Request):
        """Health check endpoint with persistence probe details."""
        persistence_backend = request.app.state.persistence_backend
        persistence_store = request.app.state.persistence_store
        payload = {
            "status": "healthy",
            "version": APP_VERSION,
            "components": {
                "api": {"status": "up"},
            },
        }

        if persistence_store is None:
            payload["components"]["persistence"] = {
                "status": "up",
                "backend": persistence_backend,
                "mode": "in-memory",
            }
            return payload

        try:
            persistence_store.ping()
            payload["components"]["persistence"] = {
                "status": "up",
                "backend": persistence_backend,
                "schema_version": persistence_store.check_schema_version(),
            }
            return payload
        except Exception:
            logger.exception("health.persistence_probe_failed backend=%s", persistence_backend)
            payload["status"] = "degraded"
            payload["components"]["persistence"] = {
                "status": "down",
                "backend": persistence_backend,
            }
            return JSONResponse(status_code=503, content=payload)

    @app.get("/")
    def root():
        """Root endpoint."""
        return {
            "message": "InstaManager API v2 - Clean Architecture",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "version": APP_VERSION,
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=load_runtime_settings().uvicorn_reload)
