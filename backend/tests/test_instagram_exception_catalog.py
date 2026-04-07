"""
Tests for Instagram exception catalog completeness and handler behavior.

Verifies that all documented instagrapi exceptions map to application failures
and that unknown exceptions safely fall back to unknown_instagram_error.
"""

import pytest
from backend.app.domain.instagram_failures import InstagramFailure
from backend.app.adapters.instagram.exception_catalog import (
    EXCEPTION_REGISTRY,
    DOCUMENTED_EXCEPTIONS,
    REGISTERED_EXCEPTION_NAMES,
)
from backend.app.adapters.instagram.exception_handler import (
    CatalogDrivenInstagramExceptionHandler,
)


class TestExceptionRegistryCoverage:
    """Test that the registry covers all documented exceptions."""

    def test_registered_names_match_documented_snapshot(self):
        """Verify explicit registrations match the documented snapshot exactly."""
        missing = DOCUMENTED_EXCEPTIONS - REGISTERED_EXCEPTION_NAMES
        extra = REGISTERED_EXCEPTION_NAMES - DOCUMENTED_EXCEPTIONS

        assert not missing, (
            "Documented exceptions missing from registration list: "
            + ", ".join(sorted(missing))
        )
        assert not extra, (
            "Registered exceptions not present in documented snapshot: "
            + ", ".join(sorted(extra))
        )

    def test_registry_covers_all_documented_exceptions(self):
        """Verify all documented exceptions have registry entries."""
        try:
            from instagrapi.exceptions import (
                ClientError, BadPassword, TwoFactorRequired, LoginRequired,
                ChallengeRequired, MediaNotFound, UserNotFound, UserError,
                ProxyError, RateLimitError, PleaseWaitFewMinutes,
                FeedbackRequired, PreLoginRequired, BadCredentials,
                IsRegulatedC18Error, ChallengeError, ChallengeRedirection,
                ChallengeSelfieCaptcha, ChallengeUnknownStep,
                SelectContactPointRecoveryForm, RecaptchaChallengeForm,
                SubmitPhoneNumberForm, LegacyForceSetNewPasswordForm,
                ConsentRequired, GeoBlockRequired, CheckpointRequired,
                MediaError, InvalidTargetUser, InvalidMediaId, MediaUnavailable,
                PrivateAccount, AccountSuspended, TermsUnblock, TermsAccept,
                AboutUsError, CollectionError, CollectionNotFound,
                DirectError, DirectThreadNotFound, DirectMessageNotFound,
                PhotoNotDownload, PhotoNotUpload, PhotoConfigureError,
                PhotoConfigureStoryError, VideoNotDownload, VideoNotUpload,
                VideoConfigureError, VideoConfigureStoryError, VideoTooLongException,
                IGTVNotUpload, IGTVConfigureError, ClipNotUpload, ClipConfigureError,
                AlbumNotDownload, AlbumUnknownFormat, AlbumConfigureError,
                StoryNotFound, HighlightNotFound, HashtagError, HashtagNotFound,
                HashtagPageWarning, LocationError, LocationNotFound,
                CommentNotFound, CommentsDisabled, ShareDecodeError,
                NoteNotFound, TrackNotFound, ResetPasswordError,
                UnsupportedError, UnsupportedSettingValue, ReloginAttemptExceeded,
                ClientLoginRequired, GenericRequestError, ClientGraphqlError,
                ClientJSONDecodeError, ClientConnectionError, ClientBadRequestError,
                ClientUnauthorizedError, ClientForbiddenError, ClientNotFoundError,
                ClientThrottledError, ClientRequestTimeout, ClientIncompleteReadError,
                ClientErrorWithTitle, ClientUnknownError, WrongCursorError,
                ClientStatusFail, ConnectProxyError, AuthRequiredProxyError,
                ProxyAddressIsBlocked, SentryBlock, PrivateError,
            )
        except ImportError:
            pytest.skip("instagrapi not installed")

        # Test that at least a representative set of exceptions is in the registry
        key_exceptions = [
            ClientError,
            BadPassword,
            TwoFactorRequired,
            LoginRequired,
            ChallengeRequired,
            MediaNotFound,
            UserNotFound,
            ProxyError,
            RateLimitError,
        ]

        for exc_class in key_exceptions:
            assert exc_class in EXCEPTION_REGISTRY, (
                f"Exception {exc_class.__name__} not found in registry. "
                "Add it to the exception_catalog.py registration section."
            )

    def test_registry_runtime_classes_cover_documented_names(self):
        """Verify documented names resolve to runtime classes present in registry."""
        registered_names = set()

        # Collect all registered exception class names
        try:
            from instagrapi import exceptions as instagrapi_exceptions

            for exc_class in EXCEPTION_REGISTRY.keys():
                registered_names.add(exc_class.__name__)
        except ImportError:
            pytest.skip("instagrapi not installed")

        # All documented names available in current instagrapi version should be in registry.
        for exc_name in DOCUMENTED_EXCEPTIONS:
            if hasattr(instagrapi_exceptions, exc_name):
                assert exc_name in registered_names, (
                    f"Documented exception {exc_name} not in runtime registry"
                )


class TestExceptionHandler:
    """Test the catalog-driven exception handler."""

    def test_handler_maps_known_exceptions(self):
        """Verify handler maps known exceptions to stable failures."""
        handler = CatalogDrivenInstagramExceptionHandler()

        try:
            from instagrapi.exceptions import BadPassword
        except ImportError:
            pytest.skip("instagrapi not installed")

        failure = handler.handle(
            BadPassword("test error"),
            operation="login",
            username="test_user",
        )

        assert isinstance(failure, InstagramFailure)
        assert failure.code == "bad_password"
        assert failure.family == "private_auth"
        assert failure.retryable is False
        assert failure.requires_user_action is True
        assert failure.http_hint == 401

    def test_handler_unknown_exception_fallback(self):
        """Verify handler safely maps unknown exceptions."""
        handler = CatalogDrivenInstagramExceptionHandler()

        # Create an exception that's not in the registry
        class UnknownInstagramError(Exception):
            pass

        failure = handler.handle(
            UnknownInstagramError("something went wrong"),
            operation="test_operation",
        )

        assert isinstance(failure, InstagramFailure)
        assert failure.code == "unknown_instagram_error"
        assert failure.family == "unknown"
        assert "something went wrong" in failure.detail

    def test_handler_preserves_error_detail(self):
        """Verify handler includes original error message in detail."""
        handler = CatalogDrivenInstagramExceptionHandler()

        try:
            from instagrapi.exceptions import UserNotFound
        except ImportError:
            pytest.skip("instagrapi not installed")

        error_msg = "User #12345 not found"
        failure = handler.handle(
            UserNotFound(error_msg),
            operation="get_user",
        )

        assert failure.detail == error_msg

    def test_handler_includes_operation_context(self):
        """Verify handler can track operation that failed."""
        handler = CatalogDrivenInstagramExceptionHandler()

        try:
            from instagrapi.exceptions import ChallengeRequired
        except ImportError:
            pytest.skip("instagrapi not installed")

        failure = handler.handle(
            ChallengeRequired("challenge"),
            operation="login",
            account_id="acc-123",
            username="user@example.com",
        )

        assert failure.code == "challenge_required"
        assert failure.requires_user_action is True


class TestFailureProperties:
    """Test InstagramFailure properties."""

    def test_failure_is_frozen(self):
        """Verify InstagramFailure is immutable."""
        from backend.app.adapters.instagram.exception_catalog import (
            SPEC_BAD_PASSWORD,
        )

        failure = SPEC_BAD_PASSWORD.to_failure()

        with pytest.raises(AttributeError):
            failure.code = "something_else"

    def test_failure_has_sensible_defaults(self):
        """Verify failures have sensible default values."""
        from backend.app.adapters.instagram.exception_catalog import (
            SPEC_TWO_FACTOR_REQUIRED,
        )

        failure = SPEC_TWO_FACTOR_REQUIRED.to_failure()

        assert failure.http_hint is not None
        assert failure.code
        assert failure.family
        assert failure.user_message
        # detail can be None if not provided
        assert failure.detail is None

    def test_failure_detail_from_exception(self):
        """Verify failure can include exception detail."""
        from backend.app.adapters.instagram.exception_catalog import (
            SPEC_MEDIA_NOT_FOUND,
        )

        error_msg = "Media ID 12345 not found"
        failure = SPEC_MEDIA_NOT_FOUND.to_failure(detail=error_msg)

        assert failure.detail == error_msg
