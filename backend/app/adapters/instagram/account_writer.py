"""
Instagram account writer adapter.

Maps self-account mutations (privacy, avatar, profile fields, presence)
through instagrapi into the InstagramAccountWriter port. Vendor types are
contained here — every method returns an AccountProfile DTO.
"""

from __future__ import annotations

from typing import Any, Optional

from app.application.dto.instagram_account_dto import AccountProfile
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.client_guard import get_guarded_client
from app.adapters.instagram.error_utils import (
    attach_instagram_failure,
    translate_instagram_error,
)


class InstagramAccountWriterAdapter:
    """Adapter for self-account mutations via instagrapi."""

    def __init__(self, client_repo: ClientRepository):
        self.client_repo = client_repo

    # ── Privacy ───────────────────────────────────────────────────────────────
    def set_private(self, account_id: str) -> AccountProfile:
        return self._privacy_toggle(
            account_id, target_private=True, operation="set_account_private"
        )

    def set_public(self, account_id: str) -> AccountProfile:
        return self._privacy_toggle(
            account_id, target_private=False, operation="set_account_public"
        )

    def _privacy_toggle(
        self, account_id: str, *, target_private: bool, operation: str
    ) -> AccountProfile:
        client = get_guarded_client(self.client_repo, account_id)
        try:
            if target_private:
                client.set_account_private()
            else:
                client.set_account_public()
            account = client.account_info()
        except Exception as exc:
            failure = translate_instagram_error(
                exc, operation=operation, account_id=account_id
            )
            raise attach_instagram_failure(
                ValueError(failure.user_message), failure
            ) from exc
        return self._map_account_to_profile(
            account, override_is_private=target_private
        )

    # ── Avatar ────────────────────────────────────────────────────────────────
    def change_avatar(self, account_id: str, image_path: str) -> AccountProfile:
        client = get_guarded_client(self.client_repo, account_id)
        try:
            client.change_profile_picture(image_path)
            account = client.account_info()
        except Exception as exc:
            failure = translate_instagram_error(
                exc, operation="change_profile_picture", account_id=account_id
            )
            raise attach_instagram_failure(
                ValueError(failure.user_message), failure
            ) from exc
        return self._map_account_to_profile(account)

    # ── Profile edit ──────────────────────────────────────────────────────────
    def edit_profile(
        self,
        account_id: str,
        *,
        first_name: Optional[str] = None,
        biography: Optional[str] = None,
        external_url: Optional[str] = None,
    ) -> AccountProfile:
        client = get_guarded_client(self.client_repo, account_id)
        kwargs: dict[str, Any] = {}
        if first_name is not None:
            kwargs["first_name"] = first_name
        if biography is not None:
            kwargs["biography"] = biography
        if external_url is not None:
            kwargs["external_url"] = external_url
        try:
            account = client.account_edit(**kwargs)
        except Exception as exc:
            failure = translate_instagram_error(
                exc, operation="account_edit", account_id=account_id
            )
            raise attach_instagram_failure(
                ValueError(failure.user_message), failure
            ) from exc
        return self._map_account_to_profile(account)

    # ── Presence ──────────────────────────────────────────────────────────────
    def set_presence_disabled(
        self, account_id: str, disabled: bool
    ) -> AccountProfile:
        client = get_guarded_client(self.client_repo, account_id)
        try:
            client.set_presence_status(disabled)
            account = client.account_info()
        except Exception as exc:
            failure = translate_instagram_error(
                exc, operation="set_presence_status", account_id=account_id
            )
            raise attach_instagram_failure(
                ValueError(failure.user_message), failure
            ) from exc
        return self._map_account_to_profile(
            account, override_presence_disabled=disabled
        )

    # ── Mapping ───────────────────────────────────────────────────────────────
    @staticmethod
    def _map_account_to_profile(
        account: Any,
        *,
        override_is_private: Optional[bool] = None,
        override_presence_disabled: Optional[bool] = None,
    ) -> AccountProfile:
        """Translate a vendor Account into the application AccountProfile DTO.

        Vendor doesn't expose presence_disabled on the Account object — when
        the caller just toggled it, the freshly-applied value is passed in via
        ``override_presence_disabled`` so callers don't see stale data.
        """
        is_private = (
            override_is_private
            if override_is_private is not None
            else getattr(account, "is_private", None)
        )
        return AccountProfile(
            id=getattr(account, "pk"),
            username=getattr(account, "username"),
            is_private=is_private,
            full_name=getattr(account, "full_name", None),
            biography=getattr(account, "biography", None),
            external_url=_to_string(getattr(account, "external_url", None)),
            profile_pic_url=_to_string(getattr(account, "profile_pic_url", None)),
            presence_disabled=override_presence_disabled,
        )


def _to_string(value: Any) -> Optional[str]:
    """Coerce instagrapi HttpUrl (pydantic) and other values to plain strings."""
    if value is None:
        return None
    return str(value)
