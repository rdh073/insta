"""
Instagrapi exception catalog and registry.

Maps all documented instagrapi exception families to stable application
failure specifications. Source of truth for vendor exception classification.

Reference: https://subzeroid.github.io/instagrapi/exceptions.html
"""

from dataclasses import dataclass
from typing import Type

from app.domain.instagram_failures import InstagramFailure


@dataclass(frozen=True)
class FailureSpec:
    """Specification for an exception family mapping."""

    code: str
    """Stable failure code (e.g., 'two_factor_required')."""

    family: str
    """Failure family (e.g., 'auth', 'challenge', 'proxy')."""

    retryable: bool
    """Whether the operation can be safely retried."""

    requires_user_action: bool
    """Whether the user must take manual action."""

    user_message: str
    """User-friendly message for UI display."""

    http_hint: int | None = None
    """Suggested HTTP status code."""

    def to_failure(self, detail: str | None = None) -> InstagramFailure:
        """Convert spec to failure instance."""
        return InstagramFailure(
            code=self.code,
            family=self.family,
            retryable=self.retryable,
            requires_user_action=self.requires_user_action,
            user_message=self.user_message,
            http_hint=self.http_hint,
            detail=detail,
        )


# ============================================================================
# Common Client Exceptions
# ============================================================================

SPEC_CLIENT_ERROR = FailureSpec(
    code="client_error",
    family="common_client",
    retryable=False,
    requires_user_action=False,
    user_message="An Instagram API error occurred.",
    http_hint=400,
)

SPEC_GENERIC_REQUEST_ERROR = FailureSpec(
    code="request_error",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Request failed. Please try again.",
    http_hint=500,
)

SPEC_CLIENT_GRAPHQL_ERROR = FailureSpec(
    code="graphql_error",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="GraphQL request failed. Please try again.",
    http_hint=500,
)

SPEC_CLIENT_JSON_DECODE_ERROR = FailureSpec(
    code="json_decode_error",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to process response. Please try again.",
    http_hint=500,
)

SPEC_CLIENT_CONNECTION_ERROR = FailureSpec(
    code="connection_error",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Connection failed. Please check your network.",
    http_hint=503,
)

SPEC_CLIENT_BAD_REQUEST_ERROR = FailureSpec(
    code="bad_request",
    family="common_client",
    retryable=False,
    requires_user_action=True,
    user_message="Invalid request. Please check your input.",
    http_hint=400,
)

SPEC_CLIENT_UNAUTHORIZED_ERROR = FailureSpec(
    code="unauthorized",
    family="common_client",
    retryable=False,
    requires_user_action=False,
    user_message="Unauthorized. Please log in again.",
    http_hint=401,
)

SPEC_CLIENT_FORBIDDEN_ERROR = FailureSpec(
    code="forbidden",
    family="common_client",
    retryable=False,
    requires_user_action=False,
    user_message="Access forbidden.",
    http_hint=403,
)

SPEC_CLIENT_NOT_FOUND_ERROR = FailureSpec(
    code="not_found",
    family="common_client",
    retryable=False,
    requires_user_action=False,
    user_message="Resource not found.",
    http_hint=404,
)

SPEC_CLIENT_THROTTLED_ERROR = FailureSpec(
    code="throttled",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Rate limited. Please wait a moment.",
    http_hint=429,
)

SPEC_CLIENT_REQUEST_TIMEOUT = FailureSpec(
    code="request_timeout",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Request timed out. Please try again.",
    http_hint=504,
)

SPEC_CLIENT_INCOMPLETE_READ_ERROR = FailureSpec(
    code="incomplete_read",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Incomplete response. Please try again.",
    http_hint=500,
)

SPEC_CLIENT_LOGIN_REQUIRED = FailureSpec(
    code="login_required",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="Login required. Please re-authenticate.",
    http_hint=401,
)

SPEC_RELOGIN_ATTEMPT_EXCEEDED = FailureSpec(
    code="relogin_attempt_exceeded",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="Too many login attempts. Please wait before trying again.",
    http_hint=429,
)

SPEC_CLIENT_ERROR_WITH_TITLE = FailureSpec(
    code="error_with_title",
    family="common_client",
    retryable=False,
    requires_user_action=False,
    user_message="An error occurred.",
    http_hint=400,
)

SPEC_CLIENT_UNKNOWN_ERROR = FailureSpec(
    code="unknown_instagram_error",
    family="unknown",
    retryable=True,
    requires_user_action=False,
    user_message="An unexpected error occurred. Please try again.",
    http_hint=500,
)

SPEC_WRONG_CURSOR_ERROR = FailureSpec(
    code="wrong_cursor",
    family="common_client",
    retryable=False,
    requires_user_action=False,
    user_message="Invalid cursor. Please try again.",
    http_hint=400,
)

SPEC_CLIENT_STATUS_FAIL = FailureSpec(
    code="status_fail",
    family="common_client",
    retryable=True,
    requires_user_action=False,
    user_message="Status check failed. Please try again.",
    http_hint=500,
)

# ============================================================================
# Proxy Exceptions
# ============================================================================

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

# ============================================================================
# Private Authentication Exceptions
# ============================================================================

SPEC_PRIVATE_ERROR = FailureSpec(
    code="private_error",
    family="private_auth",
    retryable=False,
    requires_user_action=False,
    user_message="Private account error.",
    http_hint=400,
)

SPEC_FEEDBACK_REQUIRED = FailureSpec(
    code="feedback_required",
    family="private_auth",
    retryable=True,
    requires_user_action=False,
    user_message="Action blocked temporarily. Please try later.",
    http_hint=429,
)

SPEC_PRE_LOGIN_REQUIRED = FailureSpec(
    code="pre_login_required",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="Please log in to continue.",
    http_hint=401,
)

SPEC_BAD_PASSWORD = FailureSpec(
    code="bad_password",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="Invalid password. Please check and try again.",
    http_hint=401,
)

SPEC_TWO_FACTOR_REQUIRED = FailureSpec(
    code="two_factor_required",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="Two-factor authentication required.",
    http_hint=409,
)

SPEC_BAD_CREDENTIALS = FailureSpec(
    code="bad_credentials",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="Invalid username or password.",
    http_hint=401,
)

SPEC_IS_REGULATED_C18_ERROR = FailureSpec(
    code="c18_account",
    family="private_auth",
    retryable=False,
    requires_user_action=True,
    user_message="This account is restricted due to age regulations.",
    http_hint=403,
)

# ============================================================================
# Challenge Exceptions
# ============================================================================

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

# ============================================================================
# Media Exceptions
# ============================================================================

SPEC_MEDIA_ERROR = FailureSpec(
    code="media_error",
    family="media",
    retryable=False,
    requires_user_action=False,
    user_message="Media operation failed.",
    http_hint=400,
)

SPEC_MEDIA_NOT_FOUND = FailureSpec(
    code="media_not_found",
    family="media",
    retryable=False,
    requires_user_action=False,
    user_message="Media not found.",
    http_hint=404,
)

SPEC_INVALID_TARGET_USER = FailureSpec(
    code="invalid_target_user",
    family="media",
    retryable=False,
    requires_user_action=False,
    user_message="Invalid target user.",
    http_hint=400,
)

SPEC_INVALID_MEDIA_ID = FailureSpec(
    code="invalid_media_id",
    family="media",
    retryable=False,
    requires_user_action=False,
    user_message="Invalid media ID.",
    http_hint=400,
)

SPEC_MEDIA_UNAVAILABLE = FailureSpec(
    code="media_unavailable",
    family="media",
    retryable=False,
    requires_user_action=False,
    user_message="Media is unavailable.",
    http_hint=403,
)

# ============================================================================
# User Exceptions
# ============================================================================

SPEC_USER_ERROR = FailureSpec(
    code="user_error",
    family="user",
    retryable=False,
    requires_user_action=False,
    user_message="User operation failed.",
    http_hint=400,
)

SPEC_USER_NOT_FOUND = FailureSpec(
    code="user_not_found",
    family="user",
    retryable=False,
    requires_user_action=False,
    user_message="User not found.",
    http_hint=404,
)

SPEC_PRIVATE_ACCOUNT = FailureSpec(
    code="private_account",
    family="user",
    retryable=False,
    requires_user_action=False,
    user_message="This account is private.",
    http_hint=403,
)

# ============================================================================
# Account Exceptions
# ============================================================================

SPEC_ACCOUNT_SUSPENDED = FailureSpec(
    code="account_suspended",
    family="account",
    retryable=False,
    requires_user_action=False,
    user_message="Your account has been suspended.",
    http_hint=403,
)

SPEC_TERMS_UNBLOCK = FailureSpec(
    code="terms_violation",
    family="account",
    retryable=False,
    requires_user_action=True,
    user_message="Account blocked due to terms violation.",
    http_hint=403,
)

SPEC_TERMS_ACCEPT = FailureSpec(
    code="terms_accept_required",
    family="account",
    retryable=False,
    requires_user_action=True,
    user_message="Please accept updated terms.",
    http_hint=409,
)

SPEC_ABOUT_US_ERROR = FailureSpec(
    code="about_us_error",
    family="account",
    retryable=False,
    requires_user_action=False,
    user_message="Account error.",
    http_hint=400,
)

SPEC_RESET_PASSWORD_ERROR = FailureSpec(
    code="password_reset_failed",
    family="account",
    retryable=True,
    requires_user_action=False,
    user_message="Password reset failed. Try again.",
    http_hint=400,
)

SPEC_UNSUPPORTED_ERROR = FailureSpec(
    code="unsupported_operation",
    family="account",
    retryable=False,
    requires_user_action=False,
    user_message="This operation is not supported.",
    http_hint=400,
)

SPEC_UNSUPPORTED_SETTING_VALUE = FailureSpec(
    code="unsupported_setting",
    family="account",
    retryable=False,
    requires_user_action=False,
    user_message="This setting value is not supported.",
    http_hint=400,
)

# ============================================================================
# Collection Exceptions
# ============================================================================

SPEC_COLLECTION_ERROR = FailureSpec(
    code="collection_error",
    family="collection",
    retryable=False,
    requires_user_action=False,
    user_message="Collection operation failed.",
    http_hint=400,
)

SPEC_COLLECTION_NOT_FOUND = FailureSpec(
    code="collection_not_found",
    family="collection",
    retryable=False,
    requires_user_action=False,
    user_message="Collection not found.",
    http_hint=404,
)

# ============================================================================
# Direct Exceptions
# ============================================================================

SPEC_DIRECT_ERROR = FailureSpec(
    code="direct_error",
    family="direct",
    retryable=False,
    requires_user_action=False,
    user_message="Direct message operation failed.",
    http_hint=400,
)

SPEC_DIRECT_THREAD_NOT_FOUND = FailureSpec(
    code="direct_thread_not_found",
    family="direct",
    retryable=False,
    requires_user_action=False,
    user_message="Direct thread not found.",
    http_hint=404,
)

SPEC_DIRECT_MESSAGE_NOT_FOUND = FailureSpec(
    code="direct_message_not_found",
    family="direct",
    retryable=False,
    requires_user_action=False,
    user_message="Direct message not found.",
    http_hint=404,
)

# ============================================================================
# Photo Exceptions
# ============================================================================

SPEC_PHOTO_NOT_DOWNLOAD = FailureSpec(
    code="photo_download_failed",
    family="photo",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to download photo. Try again.",
    http_hint=500,
)

SPEC_PHOTO_NOT_UPLOAD = FailureSpec(
    code="photo_upload_failed",
    family="photo",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to upload photo. Try again.",
    http_hint=500,
)

SPEC_PHOTO_CONFIGURE_ERROR = FailureSpec(
    code="photo_configure_error",
    family="photo",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to configure photo. Try again.",
    http_hint=500,
)

SPEC_PHOTO_CONFIGURE_STORY_ERROR = FailureSpec(
    code="photo_story_configure_error",
    family="photo",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to post photo story. Try again.",
    http_hint=500,
)

# ============================================================================
# Video Exceptions
# ============================================================================

SPEC_VIDEO_NOT_DOWNLOAD = FailureSpec(
    code="video_download_failed",
    family="video",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to download video. Try again.",
    http_hint=500,
)

SPEC_VIDEO_NOT_UPLOAD = FailureSpec(
    code="video_upload_failed",
    family="video",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to upload video. Try again.",
    http_hint=500,
)

SPEC_VIDEO_CONFIGURE_ERROR = FailureSpec(
    code="video_configure_error",
    family="video",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to configure video. Try again.",
    http_hint=500,
)

SPEC_VIDEO_CONFIGURE_STORY_ERROR = FailureSpec(
    code="video_story_configure_error",
    family="video",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to post video story. Try again.",
    http_hint=500,
)

SPEC_VIDEO_TOO_LONG_EXCEPTION = FailureSpec(
    code="video_too_long",
    family="video",
    retryable=False,
    requires_user_action=True,
    user_message="Video is too long.",
    http_hint=400,
)

# ============================================================================
# IGTV Exceptions
# ============================================================================

SPEC_IGTV_NOT_UPLOAD = FailureSpec(
    code="igtv_upload_failed",
    family="igtv",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to upload IGTV video. Try again.",
    http_hint=500,
)

SPEC_IGTV_CONFIGURE_ERROR = FailureSpec(
    code="igtv_configure_error",
    family="igtv",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to configure IGTV video. Try again.",
    http_hint=500,
)

# ============================================================================
# Reels/Clip Exceptions
# ============================================================================

SPEC_CLIP_NOT_UPLOAD = FailureSpec(
    code="clip_upload_failed",
    family="clip",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to upload clip. Try again.",
    http_hint=500,
)

SPEC_CLIP_CONFIGURE_ERROR = FailureSpec(
    code="clip_configure_error",
    family="clip",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to configure clip. Try again.",
    http_hint=500,
)

# ============================================================================
# Album Exceptions
# ============================================================================

SPEC_ALBUM_NOT_DOWNLOAD = FailureSpec(
    code="album_download_failed",
    family="album",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to download album. Try again.",
    http_hint=500,
)

SPEC_ALBUM_UNKNOWN_FORMAT = FailureSpec(
    code="album_unknown_format",
    family="album",
    retryable=False,
    requires_user_action=False,
    user_message="Unknown album format.",
    http_hint=400,
)

SPEC_ALBUM_CONFIGURE_ERROR = FailureSpec(
    code="album_configure_error",
    family="album",
    retryable=True,
    requires_user_action=False,
    user_message="Failed to configure album. Try again.",
    http_hint=500,
)

# ============================================================================
# Story Exceptions
# ============================================================================

SPEC_STORY_NOT_FOUND = FailureSpec(
    code="story_not_found",
    family="story",
    retryable=False,
    requires_user_action=False,
    user_message="Story not found.",
    http_hint=404,
)

# ============================================================================
# Highlight Exceptions
# ============================================================================

SPEC_HIGHLIGHT_NOT_FOUND = FailureSpec(
    code="highlight_not_found",
    family="highlight",
    retryable=False,
    requires_user_action=False,
    user_message="Highlight not found.",
    http_hint=404,
)

# ============================================================================
# Hashtag Exceptions
# ============================================================================

SPEC_HASHTAG_ERROR = FailureSpec(
    code="hashtag_error",
    family="hashtag",
    retryable=False,
    requires_user_action=False,
    user_message="Hashtag operation failed.",
    http_hint=400,
)

SPEC_HASHTAG_NOT_FOUND = FailureSpec(
    code="hashtag_not_found",
    family="hashtag",
    retryable=False,
    requires_user_action=False,
    user_message="Hashtag not found.",
    http_hint=404,
)

SPEC_HASHTAG_PAGE_WARNING = FailureSpec(
    code="hashtag_page_warning",
    family="hashtag",
    retryable=False,
    requires_user_action=False,
    user_message="Hashtag page warning.",
    http_hint=400,
)

# ============================================================================
# Location Exceptions
# ============================================================================

SPEC_LOCATION_ERROR = FailureSpec(
    code="location_error",
    family="location",
    retryable=False,
    requires_user_action=False,
    user_message="Location operation failed.",
    http_hint=400,
)

SPEC_LOCATION_NOT_FOUND = FailureSpec(
    code="location_not_found",
    family="location",
    retryable=False,
    requires_user_action=False,
    user_message="Location not found.",
    http_hint=404,
)

# ============================================================================
# Comment Exceptions
# ============================================================================

SPEC_COMMENT_NOT_FOUND = FailureSpec(
    code="comment_not_found",
    family="comment",
    retryable=False,
    requires_user_action=False,
    user_message="Comment not found.",
    http_hint=404,
)

SPEC_COMMENTS_DISABLED = FailureSpec(
    code="comments_disabled",
    family="comment",
    retryable=False,
    requires_user_action=False,
    user_message="Comments are disabled on this post.",
    http_hint=403,
)

# ============================================================================
# Share Exceptions
# ============================================================================

SPEC_SHARE_DECODE_ERROR = FailureSpec(
    code="share_decode_error",
    family="share",
    retryable=False,
    requires_user_action=False,
    user_message="Failed to decode share link.",
    http_hint=400,
)

# ============================================================================
# Note Exceptions
# ============================================================================

SPEC_NOTE_NOT_FOUND = FailureSpec(
    code="note_not_found",
    family="note",
    retryable=False,
    requires_user_action=False,
    user_message="Note not found.",
    http_hint=404,
)

# ============================================================================
# Track Exceptions
# ============================================================================

SPEC_TRACK_NOT_FOUND = FailureSpec(
    code="track_not_found",
    family="track",
    retryable=False,
    requires_user_action=False,
    user_message="Track not found.",
    http_hint=404,
)


# ============================================================================
# Exception Registry Mapping
# ============================================================================

EXCEPTION_REGISTRY: dict[type[Exception], FailureSpec] = {}
"""Maps instagrapi exception types to application failure specifications."""
_REGISTERED_EXCEPTION_NAMES: set[str] = set()
"""Names explicitly registered in this module (independent of runtime imports)."""


def _register_exception(exception_class_name: str, spec: FailureSpec) -> None:
    """
    Dynamically register an exception mapping by importing the class.

    This defers instagrapi imports to allow graceful handling if instagrapi
    is not installed, and keeps the registry size manageable.
    """
    _REGISTERED_EXCEPTION_NAMES.add(exception_class_name)
    try:
        import instagrapi.exceptions as exceptions

        if hasattr(exceptions, exception_class_name):
            exc_class = getattr(exceptions, exception_class_name)
            EXCEPTION_REGISTRY[exc_class] = spec
    except (ImportError, AttributeError):
        pass  # instagrapi not available or exception class doesn't exist


# Register all mapped exceptions
_register_exception("ClientError", SPEC_CLIENT_ERROR)
_register_exception("GenericRequestError", SPEC_GENERIC_REQUEST_ERROR)
_register_exception("ClientGraphqlError", SPEC_CLIENT_GRAPHQL_ERROR)
_register_exception("ClientJSONDecodeError", SPEC_CLIENT_JSON_DECODE_ERROR)
_register_exception("ClientConnectionError", SPEC_CLIENT_CONNECTION_ERROR)
_register_exception("ClientBadRequestError", SPEC_CLIENT_BAD_REQUEST_ERROR)
_register_exception("ClientUnauthorizedError", SPEC_CLIENT_UNAUTHORIZED_ERROR)
_register_exception("ClientForbiddenError", SPEC_CLIENT_FORBIDDEN_ERROR)
_register_exception("ClientNotFoundError", SPEC_CLIENT_NOT_FOUND_ERROR)
_register_exception("ClientThrottledError", SPEC_CLIENT_THROTTLED_ERROR)
_register_exception("ClientRequestTimeout", SPEC_CLIENT_REQUEST_TIMEOUT)
_register_exception("ClientIncompleteReadError", SPEC_CLIENT_INCOMPLETE_READ_ERROR)
_register_exception("ClientLoginRequired", SPEC_CLIENT_LOGIN_REQUIRED)
_register_exception("ReloginAttemptExceeded", SPEC_RELOGIN_ATTEMPT_EXCEEDED)
_register_exception("ClientErrorWithTitle", SPEC_CLIENT_ERROR_WITH_TITLE)
_register_exception("ClientUnknownError", SPEC_CLIENT_UNKNOWN_ERROR)
_register_exception("WrongCursorError", SPEC_WRONG_CURSOR_ERROR)
_register_exception("ClientStatusFail", SPEC_CLIENT_STATUS_FAIL)

_register_exception("ProxyError", SPEC_PROXY_ERROR)
_register_exception("ConnectProxyError", SPEC_CONNECT_PROXY_ERROR)
_register_exception("AuthRequiredProxyError", SPEC_AUTH_REQUIRED_PROXY_ERROR)
_register_exception("ProxyAddressIsBlocked", SPEC_PROXY_ADDRESS_IS_BLOCKED)
_register_exception("SentryBlock", SPEC_SENTRY_BLOCK)
_register_exception("RateLimitError", SPEC_RATE_LIMIT_ERROR)
_register_exception("PleaseWaitFewMinutes", SPEC_PLEASE_WAIT_FEW_MINUTES)

_register_exception("PrivateError", SPEC_PRIVATE_ERROR)
_register_exception("FeedbackRequired", SPEC_FEEDBACK_REQUIRED)
_register_exception("PreLoginRequired", SPEC_PRE_LOGIN_REQUIRED)
_register_exception("LoginRequired", SPEC_CLIENT_LOGIN_REQUIRED)
_register_exception("BadPassword", SPEC_BAD_PASSWORD)
_register_exception("TwoFactorRequired", SPEC_TWO_FACTOR_REQUIRED)
_register_exception("BadCredentials", SPEC_BAD_CREDENTIALS)
_register_exception("IsRegulatedC18Error", SPEC_IS_REGULATED_C18_ERROR)
_register_exception("UnknownError", SPEC_CLIENT_UNKNOWN_ERROR)

_register_exception("ChallengeError", SPEC_CHALLENGE_ERROR)
_register_exception("ChallengeRedirection", SPEC_CHALLENGE_REDIRECTION)
_register_exception("ChallengeRequired", SPEC_CHALLENGE_REQUIRED)
_register_exception("ChallengeSelfieCaptcha", SPEC_CHALLENGE_SELFIE_CAPTCHA)
_register_exception("ChallengeUnknownStep", SPEC_CHALLENGE_UNKNOWN_STEP)
_register_exception("SelectContactPointRecoveryForm", SPEC_SELECT_CONTACT_POINT_RECOVERY_FORM)
_register_exception("RecaptchaChallengeForm", SPEC_RECAPTCHA_CHALLENGE_FORM)
_register_exception("SubmitPhoneNumberForm", SPEC_SUBMIT_PHONE_NUMBER_FORM)
_register_exception("LegacyForceSetNewPasswordForm", SPEC_LEGACY_FORCE_SET_NEW_PASSWORD_FORM)
_register_exception("ConsentRequired", SPEC_CONSENT_REQUIRED)
_register_exception("GeoBlockRequired", SPEC_GEO_BLOCK_REQUIRED)
_register_exception("CheckpointRequired", SPEC_CHECKPOINT_REQUIRED)

_register_exception("MediaError", SPEC_MEDIA_ERROR)
_register_exception("MediaNotFound", SPEC_MEDIA_NOT_FOUND)
_register_exception("InvalidTargetUser", SPEC_INVALID_TARGET_USER)
_register_exception("InvalidMediaId", SPEC_INVALID_MEDIA_ID)
_register_exception("MediaUnavailable", SPEC_MEDIA_UNAVAILABLE)

_register_exception("UserError", SPEC_USER_ERROR)
_register_exception("UserNotFound", SPEC_USER_NOT_FOUND)
_register_exception("PrivateAccount", SPEC_PRIVATE_ACCOUNT)

_register_exception("AccountSuspended", SPEC_ACCOUNT_SUSPENDED)
_register_exception("TermsUnblock", SPEC_TERMS_UNBLOCK)
_register_exception("TermsAccept", SPEC_TERMS_ACCEPT)
_register_exception("AboutUsError", SPEC_ABOUT_US_ERROR)
_register_exception("ResetPasswordError", SPEC_RESET_PASSWORD_ERROR)
_register_exception("UnsupportedError", SPEC_UNSUPPORTED_ERROR)
_register_exception("UnsupportedSettingValue", SPEC_UNSUPPORTED_SETTING_VALUE)

_register_exception("CollectionError", SPEC_COLLECTION_ERROR)
_register_exception("CollectionNotFound", SPEC_COLLECTION_NOT_FOUND)

_register_exception("DirectError", SPEC_DIRECT_ERROR)
_register_exception("DirectThreadNotFound", SPEC_DIRECT_THREAD_NOT_FOUND)
_register_exception("DirectMessageNotFound", SPEC_DIRECT_MESSAGE_NOT_FOUND)

_register_exception("PhotoNotDownload", SPEC_PHOTO_NOT_DOWNLOAD)
_register_exception("PhotoNotUpload", SPEC_PHOTO_NOT_UPLOAD)
_register_exception("PhotoConfigureError", SPEC_PHOTO_CONFIGURE_ERROR)
_register_exception("PhotoConfigureStoryError", SPEC_PHOTO_CONFIGURE_STORY_ERROR)

_register_exception("VideoNotDownload", SPEC_VIDEO_NOT_DOWNLOAD)
_register_exception("VideoNotUpload", SPEC_VIDEO_NOT_UPLOAD)
_register_exception("VideoConfigureError", SPEC_VIDEO_CONFIGURE_ERROR)
_register_exception("VideoConfigureStoryError", SPEC_VIDEO_CONFIGURE_STORY_ERROR)
_register_exception("VideoTooLongException", SPEC_VIDEO_TOO_LONG_EXCEPTION)

_register_exception("IGTVNotUpload", SPEC_IGTV_NOT_UPLOAD)
_register_exception("IGTVConfigureError", SPEC_IGTV_CONFIGURE_ERROR)

_register_exception("ClipNotUpload", SPEC_CLIP_NOT_UPLOAD)
_register_exception("ClipConfigureError", SPEC_CLIP_CONFIGURE_ERROR)

_register_exception("AlbumNotDownload", SPEC_ALBUM_NOT_DOWNLOAD)
_register_exception("AlbumUnknownFormat", SPEC_ALBUM_UNKNOWN_FORMAT)
_register_exception("AlbumConfigureError", SPEC_ALBUM_CONFIGURE_ERROR)

_register_exception("StoryNotFound", SPEC_STORY_NOT_FOUND)

_register_exception("HighlightNotFound", SPEC_HIGHLIGHT_NOT_FOUND)

_register_exception("HashtagError", SPEC_HASHTAG_ERROR)
_register_exception("HashtagNotFound", SPEC_HASHTAG_NOT_FOUND)
_register_exception("HashtagPageWarning", SPEC_HASHTAG_PAGE_WARNING)

_register_exception("LocationError", SPEC_LOCATION_ERROR)
_register_exception("LocationNotFound", SPEC_LOCATION_NOT_FOUND)

_register_exception("CommentNotFound", SPEC_COMMENT_NOT_FOUND)
_register_exception("CommentsDisabled", SPEC_COMMENTS_DISABLED)

_register_exception("ShareDecodeError", SPEC_SHARE_DECODE_ERROR)

_register_exception("NoteNotFound", SPEC_NOTE_NOT_FOUND)

_register_exception("TrackNotFound", SPEC_TRACK_NOT_FOUND)


# ============================================================================
# Documented Exception List (for completeness testing)
# ============================================================================

DOCUMENTED_EXCEPTIONS = frozenset({
    "ClientError",
    "GenericRequestError",
    "ClientGraphqlError",
    "ClientJSONDecodeError",
    "ClientConnectionError",
    "ClientBadRequestError",
    "ClientUnauthorizedError",
    "ClientForbiddenError",
    "ClientNotFoundError",
    "ClientThrottledError",
    "ClientRequestTimeout",
    "ClientIncompleteReadError",
    "ClientLoginRequired",
    "ReloginAttemptExceeded",
    "ClientErrorWithTitle",
    "ClientUnknownError",
    "WrongCursorError",
    "ClientStatusFail",
    "ProxyError",
    "ConnectProxyError",
    "AuthRequiredProxyError",
    "ProxyAddressIsBlocked",
    "SentryBlock",
    "RateLimitError",
    "PleaseWaitFewMinutes",
    "PrivateError",
    "FeedbackRequired",
    "PreLoginRequired",
    "LoginRequired",
    "BadPassword",
    "TwoFactorRequired",
    "UnknownError",
    "BadCredentials",
    "IsRegulatedC18Error",
    "ChallengeError",
    "ChallengeRedirection",
    "ChallengeRequired",
    "ChallengeSelfieCaptcha",
    "ChallengeUnknownStep",
    "SelectContactPointRecoveryForm",
    "RecaptchaChallengeForm",
    "SubmitPhoneNumberForm",
    "LegacyForceSetNewPasswordForm",
    "ConsentRequired",
    "GeoBlockRequired",
    "CheckpointRequired",
    "MediaError",
    "MediaNotFound",
    "InvalidTargetUser",
    "InvalidMediaId",
    "MediaUnavailable",
    "UserError",
    "UserNotFound",
    "PrivateAccount",
    "AccountSuspended",
    "TermsUnblock",
    "TermsAccept",
    "AboutUsError",
    "CollectionError",
    "CollectionNotFound",
    "DirectError",
    "DirectThreadNotFound",
    "DirectMessageNotFound",
    "PhotoNotDownload",
    "PhotoNotUpload",
    "PhotoConfigureError",
    "PhotoConfigureStoryError",
    "VideoNotDownload",
    "VideoNotUpload",
    "VideoConfigureError",
    "VideoConfigureStoryError",
    "VideoTooLongException",
    "IGTVNotUpload",
    "IGTVConfigureError",
    "ClipNotUpload",
    "ClipConfigureError",
    "AlbumNotDownload",
    "AlbumUnknownFormat",
    "AlbumConfigureError",
    "StoryNotFound",
    "HighlightNotFound",
    "HashtagError",
    "HashtagNotFound",
    "HashtagPageWarning",
    "LocationError",
    "LocationNotFound",
    "CommentNotFound",
    "CommentsDisabled",
    "ShareDecodeError",
    "NoteNotFound",
    "TrackNotFound",
    "ResetPasswordError",
    "UnsupportedError",
    "UnsupportedSettingValue",
})

REGISTERED_EXCEPTION_NAMES = frozenset(_REGISTERED_EXCEPTION_NAMES)
"""Exception names intentionally registered in this module."""
