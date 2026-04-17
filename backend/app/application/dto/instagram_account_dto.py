"""
Instagram account DTO for write/edit operations.

Captures the subset of authenticated-account fields that are mutated by
account_writer (privacy, profile edit, avatar, presence). Returned by every
InstagramAccountWriter mutation so callers receive the post-mutation snapshot
without needing a follow-up read.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class AccountProfile:
    """Authenticated-account snapshot returned after a write mutation."""

    id: int
    """Instagram account primary key (pk)."""

    username: str
    """Account username."""

    is_private: Optional[bool] = None
    """Whether the account is private."""

    full_name: Optional[str] = None
    """Display name."""

    biography: Optional[str] = None
    """Profile bio text."""

    external_url: Optional[str] = None
    """External URL in profile (link in bio)."""

    profile_pic_url: Optional[str] = None
    """URL to profile picture."""

    presence_disabled: Optional[bool] = None
    """Whether 'last active' presence is hidden from other users."""


@dataclass(frozen=True)
class AccountConfirmationRequest:
    """Result of requesting an email or phone confirmation.

    instagrapi's ``send_confirm_email`` / ``send_confirm_phone_number`` return
    a vendor dict. We normalize the parts we recognize and preserve the rest
    in ``extra`` so the frontend can surface unknown fields without a code
    change.
    """

    account_id: str
    """Application account ID that initiated the request."""

    channel: str
    """``email`` or ``phone``."""

    target: str
    """Destination address (email or E.164 phone) the code was sent to."""

    sent: bool
    """True if the vendor accepted the request. May be False if the vendor
    returned an ok=False payload without raising."""

    message: Optional[str] = None
    """Human-readable hint from the vendor (e.g. "check your inbox")."""

    extra: dict = field(default_factory=dict)
    """Unmapped vendor fields preserved verbatim for UI surfacing."""


@dataclass(frozen=True)
class AccountSecurityInfo:
    """Snapshot of the authenticated account's security posture.

    Sourced from instagrapi's ``account_security_info()`` which returns the
    2FA state, trusted-device count, and backup-code availability.  Unknown
    vendor fields are preserved in ``extra`` so the UI can show raw metrics
    without requiring a DTO bump for every Instagram change.
    """

    account_id: str
    """Application account ID queried."""

    two_factor_enabled: Optional[bool] = None
    """True if any second factor is enabled."""

    totp_two_factor_enabled: Optional[bool] = None
    """True if an authenticator-app TOTP is enrolled."""

    sms_two_factor_enabled: Optional[bool] = None
    """True if SMS 2FA is enabled."""

    whatsapp_two_factor_enabled: Optional[bool] = None
    """True if WhatsApp 2FA is enabled."""

    backup_codes_available: Optional[bool] = None
    """True if backup codes are configured."""

    trusted_devices_count: Optional[int] = None
    """Number of trusted devices on file."""

    is_phone_confirmed: Optional[bool] = None
    """True if the phone on file is confirmed."""

    is_eligible_for_whatsapp: Optional[bool] = None
    """True if the account is eligible for WhatsApp 2FA."""

    national_number: Optional[str] = None
    """National portion of the phone number, when provided by the vendor."""

    country_code: Optional[str] = None
    """Country-code prefix associated with the phone on file."""

    extra: dict = field(default_factory=dict)
    """Unmapped vendor fields preserved verbatim for UI surfacing."""
