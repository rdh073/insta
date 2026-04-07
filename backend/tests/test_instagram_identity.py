"""
Tests for Instagram identity reader and DTO mappings.

Verifies that instagrapi Account and User objects map correctly to
stable application DTOs while handling null fields gracefully.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from app.application.dto.instagram_identity_dto import (
    AuthenticatedAccountProfile,
    PublicUserProfile,
)
from app.adapters.instagram.identity_reader import (
    InstagramIdentityReaderAdapter,
)
from app.domain.instagram_failures import InstagramAdapterError, InstagramFailure


class TestIdentityReaderAdapter:
    """Test the identity reader adapter mappings."""

    def test_authenticated_account_mapping(self):
        """Verify Account object maps correctly to AuthenticatedAccountProfile."""
        # Create a mock client with account_info() method
        mock_client = Mock()
        mock_account = Mock()
        mock_account.pk = 12345
        mock_account.username = "testuser"
        mock_account.full_name = "Test User"
        mock_account.biography = "Test bio"
        mock_account.profile_pic_url = "https://example.com/pic.jpg"
        mock_account.external_url = "https://example.com"
        mock_account.is_private = False
        mock_account.is_verified = True
        mock_account.is_business = False
        mock_account.email = "test@example.com"
        mock_account.phone_number = "+1234567890"

        mock_client.account_info.return_value = mock_account

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create adapter and test
        adapter = InstagramIdentityReaderAdapter(mock_repo)
        result = adapter.get_authenticated_account("acc-123")

        assert isinstance(result, AuthenticatedAccountProfile)
        assert result.pk == 12345
        assert result.username == "testuser"
        assert result.full_name == "Test User"
        assert result.biography == "Test bio"
        assert result.is_verified is True
        assert result.email == "test@example.com"
        assert result.phone_number == "+1234567890"

    def test_public_user_by_id_mapping(self):
        """Verify User object maps correctly to PublicUserProfile."""
        # Create a mock client with user_info() method
        mock_client = Mock()
        mock_user = Mock()
        mock_user.pk = 67890
        mock_user.username = "anotheruser"
        mock_user.full_name = "Another User"
        mock_user.biography = "Another bio"
        mock_user.profile_pic_url = "https://example.com/pic2.jpg"
        mock_user.follower_count = 1000
        mock_user.following_count = 500
        mock_user.media_count = 100
        mock_user.is_private = True
        mock_user.is_verified = False
        mock_user.is_business = False

        mock_client.user_info.return_value = mock_user

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create adapter and test
        adapter = InstagramIdentityReaderAdapter(mock_repo)
        result = adapter.get_public_user_by_id("acc-123", 67890)

        assert isinstance(result, PublicUserProfile)
        assert result.pk == 67890
        assert result.username == "anotheruser"
        assert result.follower_count == 1000
        assert result.following_count == 500
        assert result.media_count == 100
        # Verify private fields are NOT in PublicUserProfile
        assert not hasattr(result, "email")
        assert not hasattr(result, "phone_number")

    def test_public_user_by_username_mapping(self):
        """Verify user_info_by_username() maps correctly to PublicUserProfile."""
        # Create a mock client
        mock_client = Mock()
        mock_user = Mock()
        mock_user.pk = 99999
        mock_user.username = "searched_user"
        mock_user.full_name = "Searched User"
        mock_user.biography = "Found via username"
        mock_user.profile_pic_url = None
        mock_user.follower_count = 500
        mock_user.following_count = 200
        mock_user.media_count = 50
        mock_user.is_private = False
        mock_user.is_verified = False
        mock_user.is_business = True

        mock_client.user_info_by_username.return_value = mock_user

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create adapter and test
        adapter = InstagramIdentityReaderAdapter(mock_repo)
        result = adapter.get_public_user_by_username("acc-123", "searched_user")

        assert result.username == "searched_user"
        assert result.profile_pic_url is None
        assert result.is_business is True
        mock_client.user_info_by_username.assert_called_once_with("searched_user")

    def test_null_field_handling(self):
        """Verify None/null fields are handled gracefully."""
        # Create a mock client with minimal data
        mock_client = Mock()
        mock_account = Mock()
        mock_account.pk = 111
        mock_account.username = "minimal"
        mock_account.full_name = None
        mock_account.biography = None
        mock_account.profile_pic_url = None
        mock_account.external_url = None
        mock_account.is_private = None
        mock_account.is_verified = None
        mock_account.is_business = None
        mock_account.email = None
        mock_account.phone_number = None

        mock_client.account_info.return_value = mock_account

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create adapter and test
        adapter = InstagramIdentityReaderAdapter(mock_repo)
        result = adapter.get_authenticated_account("acc-123")

        assert result.pk == 111
        assert result.username == "minimal"
        assert result.full_name is None
        assert result.biography is None
        assert result.email is None

    def test_httpurl_to_string_conversion(self):
        """Verify HttpUrl fields are converted to strings."""
        from unittest.mock import Mock

        # Create a mock that behaves like pydantic's HttpUrl
        class MockHttpUrl:
            def __str__(self):
                return "https://example.com/image.jpg"

        mock_client = Mock()
        mock_account = Mock()
        mock_account.pk = 222
        mock_account.username = "urltest"
        mock_account.full_name = "URL Test"
        mock_account.biography = "Testing URL conversion"
        mock_account.profile_pic_url = MockHttpUrl()
        mock_account.external_url = None
        mock_account.is_private = False
        mock_account.is_verified = False
        mock_account.is_business = False
        mock_account.email = None
        mock_account.phone_number = None

        mock_client.account_info.return_value = mock_account

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create adapter and test
        adapter = InstagramIdentityReaderAdapter(mock_repo)
        result = adapter.get_authenticated_account("acc-123")

        assert isinstance(result.profile_pic_url, str)
        assert result.profile_pic_url == "https://example.com/image.jpg"

    def test_missing_client_error(self):
        """Verify proper error when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        # Create adapter and test
        adapter = InstagramIdentityReaderAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_authenticated_account("acc-123")

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_public_user_by_id("acc-123", 999)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_public_user_by_username("acc-123", "someone")

    def test_get_authenticated_account_raises_adapter_error_with_failure(self):
        """Vendor exception from account_info() must be wrapped in InstagramAdapterError
        with the translated InstagramFailure preserved, NOT a plain ValueError."""
        mock_client = Mock()
        mock_client.account_info.side_effect = Exception("ChallengeRequired")

        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        adapter = InstagramIdentityReaderAdapter(mock_repo)

        translated_failure = InstagramFailure(
            code="challenge_required",
            family="challenge",
            retryable=False,
            requires_user_action=True,
            user_message="Challenge required.",
            http_hint=400,
        )

        with patch(
            "app.adapters.instagram.identity_reader.translate_instagram_error",
            return_value=translated_failure,
        ):
            with pytest.raises(InstagramAdapterError) as exc_info:
                adapter.get_authenticated_account("acc-123")

        raised = exc_info.value
        # The exception message comes from failure.user_message
        assert str(raised) == "Challenge required."
        # The full failure object is preserved on exc.failure
        assert raised.failure is translated_failure
        assert raised.failure.code == "challenge_required"
        assert raised.failure.family == "challenge"

    def test_get_authenticated_account_adapter_error_not_plain_value_error(self):
        """Confirm the raised exception is InstagramAdapterError, never a bare ValueError."""
        mock_client = Mock()
        mock_client.account_info.side_effect = RuntimeError("login_required")

        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        failure = InstagramFailure(
            code="login_required",
            family="auth",
            retryable=False,
            requires_user_action=True,
            user_message="Session expired.",
            http_hint=401,
        )

        adapter = InstagramIdentityReaderAdapter(mock_repo)

        with patch(
            "app.adapters.instagram.identity_reader.translate_instagram_error",
            return_value=failure,
        ):
            with pytest.raises(InstagramAdapterError):
                adapter.get_authenticated_account("acc-123")

            # Must NOT raise a plain ValueError for API failures
            with pytest.raises(Exception) as exc_info:
                adapter.get_authenticated_account("acc-123")
            assert type(exc_info.value) is InstagramAdapterError, (
                "Expected InstagramAdapterError, got plain ValueError — failure metadata would be lost"
            )


class TestIdentityDTOs:
    """Test the identity DTO properties."""

    def test_authenticated_account_profile_frozen(self):
        """Verify AuthenticatedAccountProfile is immutable."""
        profile = AuthenticatedAccountProfile(
            pk=123,
            username="test",
            full_name="Test User",
        )

        with pytest.raises(AttributeError):
            profile.username = "modified"

    def test_public_user_profile_frozen(self):
        """Verify PublicUserProfile is immutable."""
        profile = PublicUserProfile(
            pk=456,
            username="testuser",
            follower_count=100,
        )

        with pytest.raises(AttributeError):
            profile.follower_count = 200

    def test_authenticated_account_has_private_fields(self):
        """Verify AuthenticatedAccountProfile includes private fields."""
        profile = AuthenticatedAccountProfile(
            pk=123,
            username="test",
            email="test@example.com",
            phone_number="+1234567890",
        )

        assert profile.email == "test@example.com"
        assert profile.phone_number == "+1234567890"

    def test_public_user_does_not_have_private_fields(self):
        """Verify PublicUserProfile does not have private fields."""
        profile = PublicUserProfile(
            pk=456,
            username="testuser",
        )

        # These attributes should not exist on PublicUserProfile
        assert not hasattr(profile, "email")
        assert not hasattr(profile, "phone_number")

    def test_profiles_are_distinct(self):
        """Verify the two profile types are properly distinct."""
        account_profile = AuthenticatedAccountProfile(
            pk=123,
            username="user1",
            email="user1@example.com",
        )

        user_profile = PublicUserProfile(
            pk=456,
            username="user2",
            follower_count=100,
        )

        # Different types
        assert type(account_profile) != type(user_profile)
        # Different fields
        assert hasattr(account_profile, "email")
        assert not hasattr(user_profile, "email")
        assert hasattr(user_profile, "follower_count")
        assert not hasattr(account_profile, "follower_count")
