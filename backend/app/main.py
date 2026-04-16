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
from app.application.use_cases.post_job import (
    INVALID_SCHEDULE_ERROR_CODE,
    INVALID_SCHEDULE_ERROR_MESSAGE,
    MEDIA_REQUIRED_ERROR_CODE,
    MEDIA_REQUIRED_ERROR_MESSAGE,
    has_runnable_media_paths,
    is_valid_scheduled_at,
)
from app.bootstrap.runtime import APP_VERSION, load_runtime_settings


logger = logging.getLogger("instamanager.bootstrap")
_RESTORE_ELIGIBLE_STATUSES = frozenset({"pending", "scheduled"})


def _resolve_oauth_state_secret() -> str:
    """Resolve the secret used to sign short-lived OAuth callback state."""
    return (
        os.environ.get("OAUTH_STATE_SECRET", "").strip()
        or os.environ.get("AUTH_SECRET", "").strip()
        or secrets.token_urlsafe(32)
    )


def _annotate_job_results(
    results: list[dict] | None,
    *,
    status: str,
    error: str,
    error_code: str,
) -> list:
    annotated: list = []
    for result in results or []:
        if not isinstance(result, dict):
            annotated.append(result)
            continue
        row = dict(result)
        row["status"] = status
        row["error"] = error
        row["errorCode"] = error_code
        annotated.append(row)
    return annotated


def _set_job_field(job, key: str, value) -> None:
    if isinstance(job, dict):
        job[key] = value
        return
    setattr(job, key, value)


def _get_job_field(job, key: str, default=None):
    if isinstance(job, dict):
        return job.get(key, default)
    return getattr(job, key, default)


def _job_id(job) -> str:
    if isinstance(job, dict):
        return str(job.get("id", ""))
    return str(getattr(job, "id", ""))


async def _restore_pending_jobs(job_repo, scheduler, session_restore_done: asyncio.Event) -> None:
    """Re-queue pending/scheduled jobs from persistent storage on startup.

    Required for SQL backends (sqlite/postgres) where the in-memory job store
    (state._jobs) is empty after a restart even though the DB still holds the
    job records.  Calling job_repo.set() for each job triggers the dual-write
    that repopulates state._jobs so PostJobExecutor can find the job by ID.

    Waits for session restore to finish first so accounts are authenticated
    before jobs are re-enqueued — prevents immediate failure due to missing sessions.
    """
    # Always hydrate state._jobs regardless of session readiness,
    # so stop/pause/resume work immediately after startup.
    try:
        jobs = job_repo.list_all()
    except Exception as exc:
        logger.warning("job_restore.list_failed reason=%s", exc)
        return

    # Dual-write every persisted job back to in-memory runtime state first so
    # control/status endpoints remain coherent after restart.
    for job in jobs:
        try:
            job_repo.set(_job_id(job), job)
        except Exception as exc:
            logger.warning("job_restore.hydrate_skip job_id=%s reason=%s", _job_id(job), exc)

    pending = [
        j
        for j in jobs
        if str(_get_job_field(j, "status", "")).lower() in _RESTORE_ELIGIBLE_STATUSES
    ]
    if not pending:
        return

    logger.info("job_restore.start count=%d (waiting for sessions)", len(pending))

    # Wait for session restore to complete before actually running jobs.
    try:
        await asyncio.wait_for(session_restore_done.wait(), timeout=120.0)
    except asyncio.TimeoutError:
        logger.warning("job_restore.session_wait_timeout — enqueuing anyway")

    for job in pending:
        status = str(_get_job_field(job, "status", "")).lower()
        media_paths = _get_job_field(job, "media_paths")
        if media_paths is None and hasattr(job, "get"):
            media_paths = job.get("_media_paths")

        scheduled_at = _get_job_field(job, "scheduled_at")
        if scheduled_at is None and hasattr(job, "get"):
            scheduled_at = job.get("_scheduled_at")

        if not has_runnable_media_paths(media_paths):
            _set_job_field(job, "status", "needs_media")
            _set_job_field(
                job,
                "results",
                _annotate_job_results(
                    _get_job_field(job, "results", []),
                    status="pending",
                    error=MEDIA_REQUIRED_ERROR_MESSAGE,
                    error_code=MEDIA_REQUIRED_ERROR_CODE,
                ),
            )
            try:
                job_repo.set(_job_id(job), job)
            except Exception as exc:
                logger.warning("job_restore.needs_media_persist_failed job_id=%s reason=%s", _job_id(job), exc)
            logger.info("job_restore.skip job_id=%s reason=missing_media", _job_id(job))
            continue

        if status == "scheduled" and not is_valid_scheduled_at(scheduled_at):
            _set_job_field(job, "status", "failed")
            _set_job_field(
                job,
                "results",
                _annotate_job_results(
                    _get_job_field(job, "results", []),
                    status="failed",
                    error=INVALID_SCHEDULE_ERROR_MESSAGE,
                    error_code=INVALID_SCHEDULE_ERROR_CODE,
                ),
            )
            try:
                job_repo.set(_job_id(job), job)
            except Exception as exc:
                logger.warning("job_restore.invalid_schedule_persist_failed job_id=%s reason=%s", _job_id(job), exc)
            logger.warning("job_restore.skip job_id=%s reason=invalid_schedule", _job_id(job))
            continue

        enqueue_scheduled_at = scheduled_at if status == "scheduled" else None
        try:
            scheduler.enqueue(_job_id(job), enqueue_scheduled_at)
            logger.info("job_restore.queued job_id=%s status=%s", _job_id(job), status)
        except Exception as exc:
            logger.warning("job_restore.skip job_id=%s reason=%s", _job_id(job), exc)


async def _restore_sessions(
    account_repo,
    relogin_fn,
    hydrate_fn=None,
    done_event: asyncio.Event | None = None,
    event_bus=None,
    status_lookup_fn=None,
) -> None:
    """Background task: relogin all persisted accounts on startup.

    After each successful relogin, fires profile hydration (followers/following)
    so the frontend receives account_updated SSE events without needing to poll.
    Sets done_event when all accounts are processed so job restore can proceed.
    Publishes status changes via event_bus so the Accounts page stays in sync
    without polling.
    """
    ids = account_repo.list_all_ids()
    if not ids:
        if done_event:
            done_event.set()
        return

    logger.info("session_restore.start count=%d", len(ids))

    async def _one(account_id: str) -> None:
        def _maybe_with_failure(payload: dict, source) -> dict:
            """Attach normalized failure fields from result objects when present."""
            if source is None:
                return payload
            if isinstance(source, dict):
                last_error = source.get("last_error")
                last_error_code = source.get("last_error_code")
            else:
                last_error = getattr(source, "last_error", None)
                last_error_code = getattr(source, "last_error_code", None)
            if last_error is not None:
                payload["last_error"] = last_error
            if last_error_code is not None:
                payload["last_error_code"] = last_error_code
            return payload

        try:
            result = await asyncio.to_thread(relogin_fn, account_id)
            status = "active"
            if isinstance(result, dict):
                status = str(result.get("status") or "active").lower()
            elif result is not None:
                status = str(getattr(result, "status", None) or "active").lower()

            if status != "active":
                logger.warning(
                    "session_restore.not_active account_id=%s status=%s",
                    account_id,
                    status,
                )
                if event_bus:
                    event_bus.publish(
                        "account_updated",
                        _maybe_with_failure(
                            {"id": account_id, "status": status},
                            result,
                        ),
                    )
                return

            logger.info("session_restore.ok account_id=%s", account_id)
            if event_bus:
                event_bus.publish("account_updated", {"id": account_id, "status": "active"})
            if hydrate_fn:
                try:
                    await asyncio.to_thread(hydrate_fn, account_id)
                except Exception as exc:
                    logger.debug("session_restore.hydrate_skipped account_id=%s reason=%s", account_id, exc)
        except Exception as exc:
            logger.warning("session_restore.failed account_id=%s reason=%s", account_id, exc)
            if event_bus:
                status = "error"
                if status_lookup_fn is not None:
                    try:
                        status = status_lookup_fn(account_id) or "error"
                    except Exception:
                        status = "error"
                payload = {"id": account_id, "status": status}
                failure = getattr(exc, "_instagram_failure", None)
                if failure is not None:
                    payload = _maybe_with_failure(
                        payload,
                        {
                            "last_error": getattr(failure, "user_message", None),
                            "last_error_code": getattr(failure, "code", None),
                        },
                    )
                event_bus.publish("account_updated", payload)

    # Sequential with delay — avoids rate-limiting when restoring many accounts.
    for aid in ids:
        await _one(aid)
        await asyncio.sleep(1.5)

    if done_event:
        done_event.set()
        logger.info("session_restore.done — signalling job restore")


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

        # Event that fires once all account sessions are restored.
        # _restore_pending_jobs waits on this before re-enqueueing jobs
        # so accounts are authenticated before jobs try to execute.
        sessions_ready = asyncio.Event()

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
                done_event=sessions_ready,
                event_bus=account_event_bus,
                status_lookup_fn=lambda aid: services["_status_repo"].get(aid, "error"),
            )
        )
        asyncio.ensure_future(
            _restore_pending_jobs(
                job_repo=services["_job_repo"],
                scheduler=job_queue,
                session_restore_done=sessions_ready,
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

        def _auth_error(message: str, code: str) -> JSONResponse:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": {
                        "message": message,
                        "code": code,
                        "family": "auth",
                    }
                },
            )

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
                    return _auth_error("Invalid or expired SSE token", "sse_token_invalid")
                return await call_next(request)

            # Header first; raw query param kept as last-resort fallback
            key = request.headers.get("X-API-Key", "") or request.query_params.get("x_api_key", "")
            if not secrets.compare_digest(key, _api_key):
                return _auth_error("Invalid or missing API key", "backend_api_key_invalid")
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
    from app.adapters.http.routers.direct import router as direct_router
    from app.adapters.http.routers.smart_engagement import router as smart_engagement_router
    from app.adapters.http.routers.llm_config import router as llm_config_router
    from app.adapters.http.routers.proxies import router as proxies_router
    from app.adapters.http.routers.sse import router as sse_router
    from app.adapters.http.routers.templates import router as templates_router
    from ai_copilot.api import router as ai_copilot_router

    app.include_router(accounts_router)
    app.include_router(media_proxy_router)
    app.include_router(dashboard_router)
    app.include_router(logs_router)
    app.include_router(posts_router)
    app.include_router(instagram_router)
    app.include_router(direct_router)
    # Register ai_copilot first so /api/ai/chat/graph resolves to operator copilot
    # instead of the legacy graph-chat adapter route.
    app.include_router(ai_copilot_router)
    app.include_router(ai_router)
    app.include_router(smart_engagement_router)
    app.include_router(llm_config_router)
    app.include_router(proxies_router)
    app.include_router(templates_router)
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
