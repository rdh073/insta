"""Failure specs for challenge."""

from app.adapters.instagram.exception_catalog.model import FailureSpec


SPEC_CHALLENGE_ERROR = FailureSpec(
    code="challenge_error",
    family="challenge",
    retryable=False,
    requires_user_action=False,
    user_message="Challenge error occurred.",
    http_hint=409,
)

SPEC_CHALLENGE_REDIRECTION = FailureSpec(
    code="challenge_redirection",
    family="challenge",
    retryable=False,
    requires_user_action=True,
    user_message="Challenge verification required.",
    http_hint=409,
)

SPEC_CHALLENGE_REQUIRED = FailureSpec(
    code="challenge_required",
    family="challenge",
    retryable=False,
    requires_user_action=True,
    user_message="Instagram security challenge required.",
    http_hint=409,
)

SPEC_CHALLENGE_SELFIE_CAPTCHA = FailureSpec(
    code="challenge_selfie",
    family="challenge",
    retryable=False,
    requires_user_action=True,
    user_message="Selfie verification required.",
    http_hint=409,
)

SPEC_CHALLENGE_UNKNOWN_STEP = FailureSpec(
    code="challenge_unknown_step",
    family="challenge",
    retryable=False,
    requires_user_action=True,
    user_message="Unknown challenge step. Please try again.",
    http_hint=409,
)

SPEC_SELECT_CONTACT_POINT_RECOVERY_FORM = FailureSpec(
    code="challenge_select_contact",
    family="challenge",
    retryable=False,
    requires_user_action=True,
    user_message="Select a contact method for verification.",
    http_hint=409,
)

SPEC_RECAPTCHA_CHALLENGE_FORM = FailureSpec(
    code="challenge_recaptcha",
    family="challenge",
    retryable=False,
    requires_user_action=True,
    user_message="CAPTCHA verification required.",
    http_hint=409,
)

SPEC_SUBMIT_PHONE_NUMBER_FORM = FailureSpec(
    code="challenge_phone_required",
    family="challenge",
    retryable=False,
    requires_user_action=True,
    user_message="Phone number verification required.",
    http_hint=409,
)

SPEC_LEGACY_FORCE_SET_NEW_PASSWORD_FORM = FailureSpec(
    code="challenge_password_change",
    family="challenge",
    retryable=False,
    requires_user_action=True,
    user_message="Password change required.",
    http_hint=409,
)

SPEC_CONSENT_REQUIRED = FailureSpec(
    code="consent_required",
    family="challenge",
    retryable=False,
    requires_user_action=True,
    user_message="Please accept the terms to continue.",
    http_hint=409,
)

SPEC_GEO_BLOCK_REQUIRED = FailureSpec(
    code="geo_blocked",
    family="challenge",
    retryable=False,
    requires_user_action=False,
    user_message="Your location is not supported.",
    http_hint=403,
)

SPEC_CHECKPOINT_REQUIRED = FailureSpec(
    code="checkpoint_required",
    family="challenge",
    retryable=False,
    requires_user_action=True,
    user_message="Account verification required.",
    http_hint=409,
)
