"""Encryption service for secure OAuth token storage."""

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Service for encrypting/decrypting OAuth tokens using Fernet symmetric encryption.

    The encryption key is loaded from the OAUTH_ENCRYPTION_KEY environment variable.
    If not set, a new key is generated (WARNING: this means tokens won't survive restarts).
    """

    def __init__(self, encryption_key: str | None = None):
        """
        Initialize encryption service.

        Args:
            encryption_key: Base64-encoded Fernet key. If None, loads from env or generates new.
        """
        if encryption_key:
            self.key = encryption_key.encode()
        else:
            # Load from environment
            key_str = os.getenv("OAUTH_ENCRYPTION_KEY")
            if not key_str:
                logger.warning(
                    "OAUTH_ENCRYPTION_KEY not set - generating new key. "
                    "Tokens will not survive restarts! Set OAUTH_ENCRYPTION_KEY in production."
                )
                key_str = Fernet.generate_key().decode()

            self.key = key_str.encode()

        self.cipher = Fernet(self.key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string.

        Args:
            plaintext: String to encrypt (e.g., JSON token)

        Returns:
            Base64-encoded encrypted string
        """
        try:
            encrypted_bytes = self.cipher.encrypt(plaintext.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise RuntimeError("Failed to encrypt data") from e

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string

        Raises:
            RuntimeError: If decryption fails (invalid key or corrupted data)
        """
        try:
            decrypted_bytes = self.cipher.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except InvalidToken as e:
            logger.error("Decryption failed - invalid key or corrupted data")
            raise RuntimeError("Failed to decrypt data - invalid encryption key") from e
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise RuntimeError("Failed to decrypt data") from e

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded encryption key (suitable for OAUTH_ENCRYPTION_KEY env var)
        """
        return Fernet.generate_key().decode()


# Global encryption service instance
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get or create global encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
