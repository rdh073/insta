"""Shared policy for account status and relogin mode decisions.

This module keeps challenge/auth/transient classification consistent across:
- relogin failure handling
- background hydration failure handling
- connectivity probe failure handling
- relogin mode selection from persisted error metadata
"""

from __future__ import annotations

from ...domain.instagram_failures import InstagramFailure

# Challenge-family failure codes used by this codebase's exception catalog.
# Includes non-"challenge*" codes to avoid prefix-based blind spots.
CHALLENGE_FAILURE_CODES = frozenset(
    {
        "challenge_error",
        "challenge_redirection",
        "challenge_required",
        "challenge_selfie",
        "challenge_unknown_step",
        "challenge_select_contact",
        "challenge_recaptcha",
        "challenge_phone_required",
        "challenge_password_change",
        "captcha_challenge_required",
        "checkpoint_required",
        "consent_required",
        "geo_blocked",
    }
)

_TWO_FACTOR_FAILURE_CODES = frozenset({"two_factor_required"})


def is_challenge_failure(*, code: str | None = None, family: str | None = None) -> bool:
    """Return True when metadata represents a challenge-family failure."""
    if family == "challenge":
        return True
    normalized_code = (code or "").strip()
    return normalized_code in CHALLENGE_FAILURE_CODES


def status_from_failure(
    failure: InstagramFailure,
    *,
    keep_transient: bool = True,
) -> str | None:
    """Map an InstagramFailure to account status.

    Returns:
        - "challenge" for challenge-family failures
        - "2fa_required" for explicit 2FA failures
        - None for transient retryable failures when ``keep_transient`` is True
        - "error" for all other failures
    """
    if is_challenge_failure(code=failure.code, family=failure.family):
        return "challenge"
    if failure.code in _TWO_FACTOR_FAILURE_CODES:
        return "2fa_required"
    if keep_transient and failure.retryable and not failure.requires_user_action:
        return None
    return "error"


def should_use_fresh_credentials_relogin(
    *,
    last_error_code: str | None = None,
    last_error_family: str | None = None,
) -> bool:
    """Decide whether relogin should bypass session restore.

    Fresh-credential relogin is required when the previous failure indicates:
    - server-side session invalidation (``login_required``), or
    - challenge-family outcomes (including checkpoint/consent/geo/captcha variants).
    """
    code = (last_error_code or "").strip()
    if code == "login_required":
        return True
    return is_challenge_failure(code=code, family=last_error_family)

