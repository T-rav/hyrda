"""Comprehensive tests for encryption service."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

# Add tasks to path
tasks_dir = Path(__file__).parent.parent
if str(tasks_dir) not in sys.path:
    sys.path.insert(0, str(tasks_dir))

from services.encryption_service import EncryptionService, get_encryption_service  # noqa: E402


class TestEncryptionServiceInitialization:
    """Test encryption service initialization."""

    def test_init_with_provided_key(self):
        """Test initialization with explicitly provided key."""
        test_key = Fernet.generate_key().decode()
        service = EncryptionService(encryption_key=test_key)
        assert service.key == test_key.encode()
        assert service.cipher is not None

    def test_init_with_env_key(self):
        """Test initialization loads key from environment."""
        test_key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"OAUTH_ENCRYPTION_KEY": test_key}):
            service = EncryptionService()
            assert service.key == test_key.encode()

    def test_init_without_key_generates_new(self, caplog):
        """Test that missing key generates a new one with warning."""
        with patch.dict(os.environ, {}, clear=False):
            if "OAUTH_ENCRYPTION_KEY" in os.environ:
                del os.environ["OAUTH_ENCRYPTION_KEY"]

            service = EncryptionService()
            assert service.key is not None
            assert service.cipher is not None
            # Should log warning about key generation
            assert "OAUTH_ENCRYPTION_KEY not set" in caplog.text

    def test_init_with_invalid_key_raises_error(self):
        """Test that invalid key raises error during initialization."""
        with pytest.raises(Exception):  # Fernet will raise ValueError
            EncryptionService(encryption_key="invalid-key-not-base64")


class TestEncryptionDecryption:
    """Test encryption and decryption operations."""

    @pytest.fixture
    def service(self):
        """Create service with known test key."""
        test_key = Fernet.generate_key().decode()
        return EncryptionService(encryption_key=test_key)

    def test_encrypt_decrypt_roundtrip(self, service):
        """Test that encrypted data can be decrypted back to original."""
        plaintext = "test-secret-data"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_returns_different_value(self, service):
        """Test that encryption produces different output than input."""
        plaintext = "sensitive-data"
        encrypted = service.encrypt(plaintext)
        assert encrypted != plaintext

    def test_encrypt_unicode_content(self, service):
        """Test encryption of unicode strings."""
        plaintext = "Hello 世界 🔐"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_empty_string(self, service):
        """Test encryption of empty string."""
        plaintext = ""
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_json_data(self, service):
        """Test encryption of JSON-formatted data."""
        import json

        data = {"access_token": "secret123", "expires_in": 3600}
        plaintext = json.dumps(data)
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert json.loads(decrypted) == data

    def test_encrypt_large_data(self, service):
        """Test encryption of large strings."""
        plaintext = "A" * 10000  # 10KB of data
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext


class TestDecryptionErrors:
    """Test decryption error handling."""

    @pytest.fixture
    def service(self):
        """Create service with known test key."""
        test_key = Fernet.generate_key().decode()
        return EncryptionService(encryption_key=test_key)

    def test_decrypt_with_wrong_key_raises_error(self, service):
        """Test that decryption fails with wrong key."""
        # Encrypt with first service
        plaintext = "secret-data"
        encrypted = service.encrypt(plaintext)

        # Try to decrypt with different service (different key)
        other_key = Fernet.generate_key().decode()
        other_service = EncryptionService(encryption_key=other_key)

        with pytest.raises(RuntimeError, match="Failed to decrypt data"):
            other_service.decrypt(encrypted)

    def test_decrypt_invalid_ciphertext_raises_error(self, service):
        """Test that invalid ciphertext raises error."""
        with pytest.raises(RuntimeError, match="Failed to decrypt data"):
            service.decrypt("not-valid-ciphertext")

    def test_decrypt_corrupted_data_raises_error(self, service):
        """Test that corrupted encrypted data raises error."""
        plaintext = "test-data"
        encrypted = service.encrypt(plaintext)

        # Corrupt the encrypted data
        corrupted = encrypted[:-10] + "corrupted!"

        with pytest.raises(RuntimeError, match="Failed to decrypt data"):
            service.decrypt(corrupted)

    def test_decrypt_empty_string_raises_error(self, service):
        """Test that empty ciphertext raises error."""
        with pytest.raises(RuntimeError, match="Failed to decrypt data"):
            service.decrypt("")


class TestKeyGeneration:
    """Test encryption key generation."""

    def test_generate_key_returns_valid_key(self):
        """Test that generated key is valid Fernet key."""
        key = EncryptionService.generate_key()
        # Should be able to create service with generated key
        service = EncryptionService(encryption_key=key)
        assert service.cipher is not None

    def test_generate_key_returns_different_keys(self):
        """Test that each generation produces unique keys."""
        key1 = EncryptionService.generate_key()
        key2 = EncryptionService.generate_key()
        assert key1 != key2

    def test_generate_key_is_base64_encoded(self):
        """Test that generated key is properly base64 encoded."""
        import base64

        key = EncryptionService.generate_key()
        # Should be decodable as base64
        try:
            decoded = base64.urlsafe_b64decode(key)
            assert len(decoded) == 32  # Fernet uses 32-byte keys
        except Exception:
            pytest.fail("Generated key is not valid base64")

    def test_generated_key_works_for_encryption(self):
        """Test that generated key can encrypt/decrypt data."""
        key = EncryptionService.generate_key()
        service = EncryptionService(encryption_key=key)

        plaintext = "test-data"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext


class TestGlobalServiceInstance:
    """Test global encryption service singleton."""

    def test_get_encryption_service_returns_instance(self):
        """Test that get_encryption_service returns instance."""
        # Reset global
        from services import encryption_service

        encryption_service._encryption_service = None

        service = get_encryption_service()
        assert isinstance(service, EncryptionService)

    def test_get_encryption_service_returns_same_instance(self):
        """Test that get_encryption_service returns singleton."""
        # Reset global
        from services import encryption_service

        encryption_service._encryption_service = None

        service1 = get_encryption_service()
        service2 = get_encryption_service()
        assert service1 is service2

    def test_global_service_works_for_encryption(self):
        """Test that global service can encrypt/decrypt."""
        # Reset global
        from services import encryption_service

        encryption_service._encryption_service = None

        service = get_encryption_service()
        plaintext = "global-secret"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext


class TestEncryptionServiceSecurity:
    """Test security properties of encryption."""

    @pytest.fixture
    def service(self):
        """Create service with known test key."""
        test_key = Fernet.generate_key().decode()
        return EncryptionService(encryption_key=test_key)

    def test_same_plaintext_produces_different_ciphertext(self, service):
        """Test that encrypting same data twice produces different ciphertext (IV randomization)."""
        plaintext = "same-data"
        encrypted1 = service.encrypt(plaintext)
        encrypted2 = service.encrypt(plaintext)

        # Ciphertext should be different due to random IV
        assert encrypted1 != encrypted2

        # But both should decrypt to same plaintext
        assert service.decrypt(encrypted1) == plaintext
        assert service.decrypt(encrypted2) == plaintext

    def test_encrypted_data_is_not_plaintext_substring(self, service):
        """Test that plaintext doesn't appear in ciphertext."""
        plaintext = "very-secret-password"
        encrypted = service.encrypt(plaintext)

        # Plaintext should not be visible in encrypted form
        assert plaintext not in encrypted

    def test_encrypted_data_length_differs_from_plaintext(self, service):
        """Test that encrypted data has different length than plaintext."""
        plaintext = "short"
        encrypted = service.encrypt(plaintext)

        # Encrypted data will be longer due to Fernet overhead
        assert len(encrypted) > len(plaintext)


class TestEncryptionServiceEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def service(self):
        """Create service with known test key."""
        test_key = Fernet.generate_key().decode()
        return EncryptionService(encryption_key=test_key)

    def test_encrypt_special_characters(self, service):
        """Test encryption of special characters."""
        plaintext = "!@#$%^&*()_+-={}[]|:;<>?,./"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_newlines_and_whitespace(self, service):
        """Test encryption preserves newlines and whitespace."""
        plaintext = "line1\nline2\r\nline3\ttab\t  spaces"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_binary_like_data(self, service):
        """Test encryption of binary-representable strings."""
        plaintext = "\x00\x01\x02\x03\xff"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_very_long_string(self, service):
        """Test encryption of very large data."""
        plaintext = "X" * 100000  # 100KB
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext
        assert len(decrypted) == 100000


class TestEncryptionServiceLogging:
    """Test logging behavior."""

    def test_encryption_error_logs_error(self, caplog):
        """Test that encryption errors are logged."""
        service = EncryptionService()

        # Force an error by breaking the cipher
        service.cipher = None

        with pytest.raises(RuntimeError, match="Failed to encrypt data"):
            service.encrypt("test")

        assert "Encryption failed" in caplog.text

    def test_decryption_error_logs_error(self, caplog):
        """Test that decryption errors are logged."""
        service = EncryptionService()

        with pytest.raises(RuntimeError, match="Failed to decrypt data"):
            service.decrypt("invalid-data")

        assert "Decryption failed" in caplog.text
