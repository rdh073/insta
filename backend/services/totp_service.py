from __future__ import annotations

import pyotp as _pyotp


def generate_totp_code(secret: str) -> str:
    return _pyotp.TOTP(secret).now()


def generate_totp_secret() -> str:
    return _pyotp.random_base32()


def verify_totp_code(secret: str, code: str) -> bool:
    return _pyotp.TOTP(secret).verify(code, valid_window=1)


def normalize_totp_secret(secret: str) -> str:
    return secret.replace(" ", "").upper()
