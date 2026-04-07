"""Dashboard authentication use cases.

Single-admin authentication via ADMIN_PASSWORD env var.
Issues stateless JWT tokens. No user accounts in the domain.

Required environment variables when auth is enabled:
  - ENABLE_DASHBOARD_AUTH: Set to true to enforce dashboard bearer auth
  - ADMIN_PASSWORD: The admin password (any non-empty string)
  - AUTH_SECRET: JWT signing secret (any non-empty string, different from password)
"""

from __future__ import annotations

import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional


class DashboardAuthUseCases:
    """Stateless admin authentication for dashboard access.

    Auth is pure application logic:
    - Password validated against ADMIN_PASSWORD env var
    - JWT signed with AUTH_SECRET env var
    - No DB sessions; stateless design
    """

    TOKEN_EXPIRY_HOURS: int = 24

    def __init__(self) -> None:
        self._enabled_flag = os.environ.get("ENABLE_DASHBOARD_AUTH", "")
        self._admin_password = os.environ.get("ADMIN_PASSWORD", "")
        self._auth_secret = os.environ.get("AUTH_SECRET", "")

    def is_enabled(self) -> bool:
        """Return True when dashboard bearer auth is explicitly configured."""
        enabled = self._enabled_flag.strip().lower() in {"1", "true", "yes", "on"}
        return enabled and bool(self._admin_password and self._auth_secret)

    def _check_configured(self) -> None:
        """Fail fast if env vars are missing."""
        if not self._admin_password:
            raise RuntimeError(
                "ADMIN_PASSWORD env var is required but not set. "
                "Set it before starting the application."
            )
        if not self._auth_secret:
            raise RuntimeError(
                "AUTH_SECRET env var is required but not set. "
                "Set it before starting the application."
            )

    def login(self, password: str) -> str:
        """Validate admin password and issue a JWT.

        Args:
            password: Password to validate.

        Returns:
            JWT token string.

        Raises:
            PermissionError: If password is wrong.
            RuntimeError: If env vars are not configured.
        """
        self._check_configured()

        # Timing-safe comparison to prevent timing attacks
        provided = password.encode("utf-8") if isinstance(password, str) else password
        expected = self._admin_password.encode("utf-8")

        if not hmac.compare_digest(provided, expected):
            raise PermissionError("Invalid admin password")

        return self._issue_token()

    def validate(self, token: str) -> bool:
        """Validate a JWT token.

        Args:
            token: Bearer token to validate.

        Returns:
            True if valid and not expired, False otherwise.
        """
        try:
            self._decode_token(token)
            return True
        except Exception:
            return False

    def _issue_token(self) -> str:
        """Issue a signed JWT with 24h expiry."""
        try:
            import jwt as pyjwt  # PyJWT
        except ImportError:
            raise RuntimeError(
                "PyJWT is required for dashboard auth. "
                "Install it: pip install PyJWT"
            )

        now = datetime.now(timezone.utc)
        payload = {
            "sub": "admin",
            "iat": now,
            "exp": now + timedelta(hours=self.TOKEN_EXPIRY_HOURS),
        }
        return pyjwt.encode(payload, self._auth_secret, algorithm="HS256")

    def _decode_token(self, token: str) -> dict:
        """Decode and validate a JWT. Raises on any failure."""
        try:
            import jwt as pyjwt  # PyJWT
        except ImportError:
            raise RuntimeError("PyJWT is required for dashboard auth.")

        return pyjwt.decode(
            token,
            self._auth_secret,
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
