"""HTTP-layer observability utilities."""

from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger("instamanager.http")


def register_observability(app: FastAPI, *, enable_request_logging: bool) -> None:
    """Attach request logging middleware and exception handlers."""

    if enable_request_logging:

        @app.middleware("http")
        async def request_logging_middleware(request: Request, call_next):
            request_id = _ensure_request_id(request)
            start = perf_counter()
            response = await call_next(request)
            duration_ms = (perf_counter() - start) * 1000
            response.headers.setdefault("X-Request-ID", request_id)
            logger.info(
                "request.complete method=%s path=%s status_code=%s duration_ms=%.2f request_id=%s client=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                request_id,
                request.client.host if request.client else "-",
            )
            return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = _ensure_request_id(request)
        logger.warning(
            "request.validation_error method=%s path=%s request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )
        response = JSONResponse(
            status_code=422,
            content={
                "detail": "Request validation failed",
                "errors": exc.errors(),
                "request_id": request_id,
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        request_id = _ensure_request_id(request)
        log_fn = logger.warning if exc.status_code >= 400 else logger.info
        log_fn(
            "request.http_error method=%s path=%s status_code=%s request_id=%s",
            request.method,
            request.url.path,
            exc.status_code,
            request_id,
        )
        response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": request_id},
        )
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = _ensure_request_id(request)
        logger.exception(
            "request.unhandled_exception method=%s path=%s request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )
        response = JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response


def _ensure_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id

    header_request_id = request.headers.get("X-Request-ID")
    request_id = header_request_id or str(uuid4())
    request.state.request_id = request_id
    return request_id
