"""App-owned TOTP adapter.

Implements TOTPManager port using pyotp directly.
No dependency on root-layer TOTP helpers or adapters.
"""

from __future__ import annotations

from typing import Optional

import pyotp


class TOTPAdapter:
    """Implements app.application.ports.adapters.TOTPManager via pyotp."""

    def generate_code(self, secret: str) -> str:
        """Generate current TOTP code from secret."""
        return pyotp.TOTP(secret).now()

    def generate_secret(self) -> str:
        """Generate a new random TOTP secret (base32-encoded)."""
        return pyotp.random_base32()

    def get_provisioning_uri(self, secret: str, name: str) -> str:
        """Get QR code provisioning URI for authenticator apps."""
        return pyotp.TOTP(secret).provisioning_uri(
            name=name,
            issuer_name="InstaManager",
        )

    def verify_code(self, secret: str, code: str) -> bool:
        """Verify TOTP code, allowing ±1 window for clock skew."""
        return pyotp.TOTP(secret).verify(code, valid_window=1)

    def normalize_secret(self, secret: str) -> Optional[str]:
        """Strip spaces and uppercase — accepts user input like '2OWR 5YTV ZHAN 66UJ'."""
        if not secret:
            return None
        return secret.replace(" ", "").upper()
