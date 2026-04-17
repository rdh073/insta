"""Account edit use cases - self-account mutations.

Owns precondition enforcement (account exists + authenticated) and
input validation (biography length, URL shape, image readability) before
delegating to the InstagramAccountWriter port.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

from app.application.dto.instagram_account_dto import (
    AccountConfirmationRequest,
    AccountProfile,
)

if TYPE_CHECKING:
    from app.application.ports.instagram_account_writer import InstagramAccountWriter
    from app.application.ports.repositories import AccountRepository, ClientRepository


_BIOGRAPHY_MAX_LEN = 150
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9\-\s]{5,}$")


class AccountEditUseCases:
    """Self-account mutations: privacy, avatar, profile fields, presence."""

    def __init__(
        self,
        account_repo: "AccountRepository",
        client_repo: "ClientRepository",
        account_writer: "InstagramAccountWriter",
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.account_writer = account_writer

    # ── Preconditions ────────────────────────────────────────────────────────
    def _require_authenticated(self, account_id: str) -> None:
        if not self.account_repo.get(account_id):
            raise ValueError(f"Account {account_id!r} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id!r} is not authenticated")

    # ── Privacy ───────────────────────────────────────────────────────────────
    def set_private(self, account_id: str) -> AccountProfile:
        self._require_authenticated(account_id)
        return self.account_writer.set_private(account_id)

    def set_public(self, account_id: str) -> AccountProfile:
        self._require_authenticated(account_id)
        return self.account_writer.set_public(account_id)

    # ── Avatar ────────────────────────────────────────────────────────────────
    def change_avatar(self, account_id: str, image_path: str) -> AccountProfile:
        self._require_authenticated(account_id)
        if not isinstance(image_path, str) or not image_path.strip():
            raise ValueError("image_path must be a non-empty string")
        path = image_path.strip()
        if not os.path.isfile(path):
            raise ValueError(f"image_path does not exist: {path!r}")
        if not os.access(path, os.R_OK):
            raise ValueError(f"image_path is not readable: {path!r}")
        return self.account_writer.change_avatar(account_id, path)

    # ── Profile edit ──────────────────────────────────────────────────────────
    def edit_profile(
        self,
        account_id: str,
        *,
        first_name: Optional[str] = None,
        biography: Optional[str] = None,
        external_url: Optional[str] = None,
    ) -> AccountProfile:
        self._require_authenticated(account_id)

        if first_name is None and biography is None and external_url is None:
            raise ValueError(
                "edit_profile requires at least one of first_name, biography, external_url"
            )

        if biography is not None and len(biography) > _BIOGRAPHY_MAX_LEN:
            raise ValueError(
                f"biography exceeds {_BIOGRAPHY_MAX_LEN} characters "
                f"(got {len(biography)})"
            )

        if external_url is not None and external_url != "":
            parsed = urlparse(external_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(
                    f"external_url must be an absolute http(s) URL, got {external_url!r}"
                )

        return self.account_writer.edit_profile(
            account_id,
            first_name=first_name,
            biography=biography,
            external_url=external_url,
        )

    # ── Presence ──────────────────────────────────────────────────────────────
    def set_presence_disabled(
        self, account_id: str, disabled: bool
    ) -> AccountProfile:
        self._require_authenticated(account_id)
        if not isinstance(disabled, bool):
            raise ValueError(f"disabled must be a bool, got {type(disabled).__name__}")
        return self.account_writer.set_presence_disabled(account_id, disabled)

    # ── Contact confirmation ─────────────────────────────────────────────────
    def request_email_confirm(
        self, account_id: str, email: str
    ) -> AccountConfirmationRequest:
        """Ask Instagram to deliver a code to ``email``.

        The operator must submit the received code in a separate step (not yet
        wired — tracked alongside the second-step confirmation token work).
        """
        self._require_authenticated(account_id)
        if not isinstance(email, str):
            raise ValueError("email must be a string")
        normalized = email.strip()
        if not _EMAIL_RE.match(normalized):
            raise ValueError(f"email is not a valid address: {email!r}")
        return self.account_writer.request_email_confirm(account_id, normalized)

    def request_phone_confirm(
        self, account_id: str, phone: str
    ) -> AccountConfirmationRequest:
        """Ask Instagram to deliver a code to ``phone``.

        Accepts E.164 (``+1555...``) or national formats with digits/dashes.
        """
        self._require_authenticated(account_id)
        if not isinstance(phone, str):
            raise ValueError("phone must be a string")
        normalized = phone.strip()
        if not _PHONE_RE.match(normalized):
            raise ValueError(f"phone is not a valid phone number: {phone!r}")
        return self.account_writer.request_phone_confirm(account_id, normalized)
