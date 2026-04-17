"""Unit tests for InstagramAccountSecurityReaderAdapter PII projection.

Regression guard: the _map() function must never include PII fields
(birthday, phone_number, email, supervision_info, interop_messaging_user_fbid,
pk_id, fbid_v2) in the extra dict, even if Instagram's account_security_info()
response gains those keys in the future.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.adapters.instagram.account_security_reader import (
    InstagramAccountSecurityReaderAdapter,
    _PII_SECURITY_KEYS,
)

_ACCOUNT_ID = "acc-001"

_FORBIDDEN_KEYS = {
    "birthday",
    "phone_number",
    "email",
    "supervision_info",
    "interop_messaging_user_fbid",
    "pk_id",
    "fbid_v2",
}


class TestAccountSecurityReaderPIIProjection:
    def test_pii_keys_absent_from_extra_when_present_in_raw(self):
        """PII keys in the raw payload must not appear in the mapped DTO's extra."""
        raw = {
            "is_two_factor_enabled": True,
            "is_totp_two_factor_enabled": False,
            "is_sms_two_factor_enabled": True,
            "is_whatsapp_two_factor_enabled": False,
            "is_phone_confirmed": True,
            "is_eligible_for_whatsapp_two_factor": False,
            "backup_codes": ["abc123"],
            "trusted_devices": [],
            "national_number": "5551234567",
            "country_code": "1",
            "status": "ok",
            # Forbidden PII keys:
            "birthday": "1990-01-01",
            "phone_number": "+15551234567",
            "email": "user@example.com",
            "supervision_info": {"family_center_url": "https://example.com/fc/"},
            "interop_messaging_user_fbid": "12345678901234",
            "pk_id": "67890123456",
            "fbid_v2": "98765432109",
        }

        info = InstagramAccountSecurityReaderAdapter._map(_ACCOUNT_ID, raw)

        for key in _FORBIDDEN_KEYS:
            assert key not in info.extra, (
                f"PII key {key!r} must not appear in AccountSecurityInfo.extra"
            )

    def test_extra_contains_only_safe_unknown_keys(self):
        """Unknown non-PII keys pass through to extra; PII keys are dropped."""
        raw = {
            "birthday": "1990-05-15",
            "phone_number": "+15551234567",
            "email": "secret@example.com",
            "supervision_info": {"url": "..."},
            "interop_messaging_user_fbid": "99999",
            "pk_id": "11111",
            "fbid_v2": "22222",
            "some_unknown_safe_key": "safe_value",
            "another_safe_unknown": 42,
        }

        info = InstagramAccountSecurityReaderAdapter._map(_ACCOUNT_ID, raw)

        # All forbidden keys must be absent
        for key in _FORBIDDEN_KEYS:
            assert key not in info.extra

        # Safe unknown keys must still pass through
        assert info.extra.get("some_unknown_safe_key") == "safe_value"
        assert info.extra.get("another_safe_unknown") == 42

    def test_pii_security_keys_constant_covers_required_fields(self):
        """_PII_SECURITY_KEYS must cover all fields listed in the task spec."""
        required = {
            "birthday",
            "phone_number",
            "email",
            "supervision_info",
            "interop_messaging_user_fbid",
            "pk_id",
            "fbid_v2",
        }
        missing = required - _PII_SECURITY_KEYS
        assert not missing, f"Missing PII keys in _PII_SECURITY_KEYS: {missing}"

    def test_known_security_fields_are_still_mapped(self):
        """2FA/backup/device fields must still be mapped correctly."""
        raw = {
            "is_two_factor_enabled": True,
            "is_totp_two_factor_enabled": True,
            "is_sms_two_factor_enabled": False,
            "is_whatsapp_two_factor_enabled": False,
            "backup_codes": ["code1", "code2"],
            "trusted_devices": [{"id": "dev1"}, {"id": "dev2"}],
            "national_number": "5551234567",
            "country_code": "1",
        }

        info = InstagramAccountSecurityReaderAdapter._map(_ACCOUNT_ID, raw)

        assert info.two_factor_enabled is True
        assert info.totp_two_factor_enabled is True
        assert info.backup_codes_available is True
        assert info.trusted_devices_count == 2
        assert info.national_number == "5551234567"
        assert info.country_code == "1"

    def test_empty_raw_payload_produces_empty_extra(self):
        """An empty raw payload produces a DTO with None fields and empty extra."""
        info = InstagramAccountSecurityReaderAdapter._map(_ACCOUNT_ID, {})

        assert info.account_id == _ACCOUNT_ID
        assert info.two_factor_enabled is None
        assert info.extra == {}
