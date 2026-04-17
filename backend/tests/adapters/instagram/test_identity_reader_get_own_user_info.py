"""Unit tests for InstagramIdentityReaderAdapter.get_own_user_info().

Pins the endpoint used (user_info(user_id) → /api/v1/users/{id}/info/) and
verifies that follower_count, following_count, and media_count are mapped into
the returned PublicUserProfile.  This is the adapter that fixes the
followers: null regression caused by calling account_info() instead.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.adapters.instagram.identity_reader import InstagramIdentityReaderAdapter
from app.application.dto.instagram_identity_dto import PublicUserProfile


_ACCOUNT_ID = "acc-001"
_USER_PK = 123456789


def _make_mock_user(
    *,
    pk: int = _USER_PK,
    username: str = "doloresball269",
    full_name: str = "Dolores Ball",
    biography: str = "Bio text",
    profile_pic_url=None,
    follower_count: int = 4200,
    following_count: int = 310,
    media_count: int = 87,
    is_private: bool = False,
    is_verified: bool = False,
    is_business: bool = False,
) -> MagicMock:
    user = MagicMock()
    user.pk = pk
    user.username = username
    user.full_name = full_name
    user.biography = biography
    user.profile_pic_url = profile_pic_url
    user.follower_count = follower_count
    user.following_count = following_count
    user.media_count = media_count
    user.is_private = is_private
    user.is_verified = is_verified
    user.is_business = is_business
    return user


def _make_adapter_with_client(mock_client: MagicMock) -> InstagramIdentityReaderAdapter:
    client_repo = MagicMock()
    client_repo.get.return_value = mock_client
    with patch(
        "app.adapters.instagram.identity_reader.get_guarded_client",
        return_value=mock_client,
    ):
        adapter = InstagramIdentityReaderAdapter(client_repo)
    return adapter, client_repo


class TestGetOwnUserInfo:
    def test_returns_public_user_profile(self):
        mock_client = MagicMock()
        mock_client.user_id = _USER_PK
        mock_user = _make_mock_user()
        mock_client.user_info_v1.return_value = mock_user

        adapter = InstagramIdentityReaderAdapter(MagicMock())

        with patch(
            "app.adapters.instagram.identity_reader.get_guarded_client",
            return_value=mock_client,
        ):
            result = adapter.get_own_user_info(_ACCOUNT_ID)

        assert isinstance(result, PublicUserProfile)

    def test_calls_user_info_with_own_user_id(self):
        """Must call user_info_v1(client.user_id) — the direct private-v1
        endpoint — not user_info() which tries graphql first and retries 6x
        on 401, and not account_info() which hits the legacy edit endpoint.
        """
        mock_client = MagicMock()
        mock_client.user_id = _USER_PK
        mock_client.user_info_v1.return_value = _make_mock_user()

        adapter = InstagramIdentityReaderAdapter(MagicMock())

        with patch(
            "app.adapters.instagram.identity_reader.get_guarded_client",
            return_value=mock_client,
        ):
            adapter.get_own_user_info(_ACCOUNT_ID)

        mock_client.user_info_v1.assert_called_once_with(_USER_PK)
        mock_client.user_info.assert_not_called()
        mock_client.account_info.assert_not_called()

    def test_follower_count_is_populated(self):
        mock_client = MagicMock()
        mock_client.user_id = _USER_PK
        mock_client.user_info_v1.return_value = _make_mock_user(follower_count=4200)

        adapter = InstagramIdentityReaderAdapter(MagicMock())

        with patch(
            "app.adapters.instagram.identity_reader.get_guarded_client",
            return_value=mock_client,
        ):
            result = adapter.get_own_user_info(_ACCOUNT_ID)

        assert result.follower_count == 4200

    def test_following_count_is_populated(self):
        mock_client = MagicMock()
        mock_client.user_id = _USER_PK
        mock_client.user_info_v1.return_value = _make_mock_user(following_count=310)

        adapter = InstagramIdentityReaderAdapter(MagicMock())

        with patch(
            "app.adapters.instagram.identity_reader.get_guarded_client",
            return_value=mock_client,
        ):
            result = adapter.get_own_user_info(_ACCOUNT_ID)

        assert result.following_count == 310

    def test_media_count_is_populated(self):
        mock_client = MagicMock()
        mock_client.user_id = _USER_PK
        mock_client.user_info_v1.return_value = _make_mock_user(media_count=87)

        adapter = InstagramIdentityReaderAdapter(MagicMock())

        with patch(
            "app.adapters.instagram.identity_reader.get_guarded_client",
            return_value=mock_client,
        ):
            result = adapter.get_own_user_info(_ACCOUNT_ID)

        assert result.media_count == 87

    def test_zero_followers_is_not_null(self):
        """A zero count must map to 0 (int), not None."""
        mock_client = MagicMock()
        mock_client.user_id = _USER_PK
        mock_client.user_info_v1.return_value = _make_mock_user(
            follower_count=0, following_count=0, media_count=0
        )

        adapter = InstagramIdentityReaderAdapter(MagicMock())

        with patch(
            "app.adapters.instagram.identity_reader.get_guarded_client",
            return_value=mock_client,
        ):
            result = adapter.get_own_user_info(_ACCOUNT_ID)

        assert result.follower_count == 0
        assert result.following_count == 0
        assert result.media_count == 0

    def test_raises_instagram_adapter_error_on_api_failure(self):
        from app.domain.instagram_failures import InstagramAdapterError

        mock_client = MagicMock()
        mock_client.user_id = _USER_PK
        mock_client.user_info_v1.side_effect = Exception("network error")

        adapter = InstagramIdentityReaderAdapter(MagicMock())

        with patch(
            "app.adapters.instagram.identity_reader.get_guarded_client",
            return_value=mock_client,
        ), patch(
            "app.adapters.instagram.identity_reader.translate_instagram_error",
        ) as mock_translate:
            mock_failure = MagicMock()
            mock_failure.user_message = "Instagram API error"
            mock_translate.return_value = mock_failure

            with pytest.raises(InstagramAdapterError):
                adapter.get_own_user_info(_ACCOUNT_ID)
