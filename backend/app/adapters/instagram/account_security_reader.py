"""Instagram account security reader adapter.

Wraps instagrapi's ``account_security_info()`` and translates the raw dict
into the ``AccountSecurityInfo`` DTO. Kept separate from ``identity_reader``
so callers can distinguish public-profile reads from sensitive security
state (2FA, backup codes, trusted devices).
"""

from __future__ import annotations

from typing import Any, Optional

from app.application.dto.instagram_account_dto import AccountSecurityInfo
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.client_guard import get_guarded_client
from app.adapters.instagram.error_utils import (
    attach_instagram_failure,
    translate_instagram_error,
)


_KNOWN_SECURITY_KEYS = {
    "is_two_factor_enabled",
    "is_totp_two_factor_enabled",
    "is_sms_two_factor_enabled",
    "is_whatsapp_two_factor_enabled",
    "is_phone_confirmed",
    "is_eligible_for_whatsapp_two_factor",
    "backup_codes",
    "trusted_devices",
    "national_number",
    "country_code",
    "status",
}


class InstagramAccountSecurityReaderAdapter:
    """Adapter for reading the authenticated account's security posture."""

    def __init__(self, client_repo: ClientRepository):
        self.client_repo = client_repo

    def get_account_security_info(self, account_id: str) -> AccountSecurityInfo:
        client = get_guarded_client(self.client_repo, account_id)
        try:
            raw = client.account_security_info()
        except Exception as exc:
            failure = translate_instagram_error(
                exc, operation="account_security_info", account_id=account_id
            )
            raise attach_instagram_failure(
                ValueError(failure.user_message), failure
            ) from exc
        return self._map(account_id, raw)

    @staticmethod
    def _map(account_id: str, raw: Any) -> AccountSecurityInfo:
        payload: dict = raw if isinstance(raw, dict) else {}

        backup_codes = payload.get("backup_codes")
        backup_codes_available: Optional[bool]
        if backup_codes is None:
            backup_codes_available = None
        else:
            backup_codes_available = bool(backup_codes)

        trusted = payload.get("trusted_devices")
        trusted_count: Optional[int]
        if isinstance(trusted, list):
            trusted_count = len(trusted)
        elif isinstance(trusted, int):
            trusted_count = trusted
        else:
            trusted_count = None

        extra = {
            k: v for k, v in payload.items() if k not in _KNOWN_SECURITY_KEYS
        }

        return AccountSecurityInfo(
            account_id=account_id,
            two_factor_enabled=_opt_bool(payload.get("is_two_factor_enabled")),
            totp_two_factor_enabled=_opt_bool(
                payload.get("is_totp_two_factor_enabled")
            ),
            sms_two_factor_enabled=_opt_bool(
                payload.get("is_sms_two_factor_enabled")
            ),
            whatsapp_two_factor_enabled=_opt_bool(
                payload.get("is_whatsapp_two_factor_enabled")
            ),
            backup_codes_available=backup_codes_available,
            trusted_devices_count=trusted_count,
            is_phone_confirmed=_opt_bool(payload.get("is_phone_confirmed")),
            is_eligible_for_whatsapp=_opt_bool(
                payload.get("is_eligible_for_whatsapp_two_factor")
            ),
            national_number=_opt_str(payload.get("national_number")),
            country_code=_opt_str(payload.get("country_code")),
            extra=extra,
        )


def _opt_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    return bool(value)


def _opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)
