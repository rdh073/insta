"""Fernet encryption service for API key storage.

Adapter-internal: application layer never calls this.
Keys are encrypted before writing to DB and decrypted after reading.

Required env var:
  ENCRYPTION_KEY — base64url-encoded 32-byte Fernet key.
  Generate once with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

import os


class CryptoService:
    """Fernet-based symmetric encryption for sensitive field storage.

    This service is adapter-internal. It must NOT be exposed to the
    application or domain layers. The application always works with
    plaintext values; only the persistence adapter calls this.
    """

    def __init__(self) -> None:
        key = os.environ.get("ENCRYPTION_KEY", "")
        if not key:
            raise RuntimeError(
                "ENCRYPTION_KEY env var is required but not set. "
                "Generate a key with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        try:
            from cryptography.fernet import Fernet
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            raise RuntimeError(
                f"ENCRYPTION_KEY is invalid: {e}. "
                "Regenerate it with Fernet.generate_key()."
            ) from e

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string to a base64-encoded ciphertext.

        Args:
            plaintext: String to encrypt.

        Returns:
            Base64-encoded encrypted string.
        """
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a base64-encoded ciphertext to plaintext.

        Args:
            ciphertext: Encrypted string to decrypt.

        Returns:
            Original plaintext string.

        Raises:
            ValueError: If decryption fails (tampered or wrong key).
        """
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to decrypt value: {e}") from e
