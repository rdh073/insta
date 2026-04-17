"""Instagram account security reader port.

Kept as a standalone reader (separate from identity_reader) to preserve
single-responsibility: identity reads expose the public-facing profile
shape, security reads expose 2FA state + trusted-device posture and must
be treated as sensitive data by callers.
"""

from typing import Protocol

from app.application.dto.instagram_account_dto import AccountSecurityInfo


class InstagramAccountSecurityReader(Protocol):
    """Port for reading the authenticated account's security posture."""

    def get_account_security_info(self, account_id: str) -> AccountSecurityInfo:
        """Fetch the 2FA / trusted-device snapshot for ``account_id``.

        Calls ``Client.account_security_info()`` on the authenticated client.

        Returns:
            AccountSecurityInfo with the fields the vendor exposed; unknown
            keys are preserved in ``extra``.

        Raises:
            ValueError: If the account is not found or not authenticated.
        """
        ...
