"""Failure specs for proxy."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_PROXY_ERROR = FailureSpec(
    code="proxy_error",
    family="proxy",
    retryable=True,
    requires_user_action=True,
    user_message="Proxy configuration error. Please check your proxy.",
    http_hint=503,
)

SPEC_CONNECT_PROXY_ERROR = FailureSpec(
    code="proxy_connection_failed",
    family="proxy",
    retryable=True,
    requires_user_action=True,
    user_message="Cannot connect to proxy. Please verify settings.",
    http_hint=503,
)

SPEC_AUTH_REQUIRED_PROXY_ERROR = FailureSpec(
    code="proxy_auth_failed",
    family="proxy",
    retryable=False,
    requires_user_action=True,
    user_message="Proxy authentication failed. Check credentials.",
    http_hint=407,
)

SPEC_PROXY_ADDRESS_IS_BLOCKED = FailureSpec(
    code="proxy_blocked",
    family="proxy",
    retryable=True,
    requires_user_action=True,
    user_message="Your proxy is blocked. Please change it.",
    http_hint=503,
)

SPEC_SENTRY_BLOCK = FailureSpec(
    code="ip_banned",
    family="proxy",
    retryable=True,
    requires_user_action=True,
    user_message="Your IP address appears to be banned. Try a different proxy.",
    http_hint=503,
)

SPEC_RATE_LIMIT_ERROR = FailureSpec(
    code="rate_limit",
    family="proxy",
    retryable=True,
    requires_user_action=False,
    user_message="Rate limited. Please wait before trying again.",
    http_hint=429,
)

SPEC_PLEASE_WAIT_FEW_MINUTES = FailureSpec(
    code="wait_required",
    family="proxy",
    retryable=True,
    requires_user_action=False,
    user_message="Please wait a few minutes before trying again.",
    http_hint=429,
)
