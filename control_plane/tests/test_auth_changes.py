"""Tests for authentication changes (OAuth scope fix and domain verification)."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add control_plane to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDomainVerification:
    """Test domain verification logic for wildcard support."""

    def test_wildcard_domain_allows_all_emails(self):
        """Test that wildcard domain allows any email."""
        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "*"}, clear=False):
            # Reimport to pick up env var
            import importlib
            import utils.auth
            importlib.reload(utils.auth)
            from utils.auth import verify_domain

            assert verify_domain("user@example.com") is True
            assert verify_domain("admin@test.org") is True
            assert verify_domain("anyone@anywhere.co") is True

    def test_specific_domain_only_allows_matching_emails(self):
        """Test that specific domain only allows matching emails."""
        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "8thlight.com"}, clear=False):
            import importlib
            import utils.auth
            importlib.reload(utils.auth)
            from utils.auth import verify_domain

            assert verify_domain("user@8thlight.com") is True
            assert verify_domain("admin@8thlight.com") is True
            assert verify_domain("user@example.com") is False
            assert verify_domain("admin@test.org") is False

    def test_empty_email_returns_false(self):
        """Test that empty email returns False."""
        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "*"}, clear=False):
            import importlib
            import utils.auth
            importlib.reload(utils.auth)
            from utils.auth import verify_domain

            assert verify_domain("") is False
            # The function handles None gracefully with "if not email" check
            assert verify_domain(None) is False

    def test_malformed_email_without_at_returns_false(self):
        """Test that email without @ returns False."""
        with patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAIN": "8thlight.com"}, clear=False):
            import importlib
            import utils.auth
            importlib.reload(utils.auth)
            from utils.auth import verify_domain

            # These don't have @ so endswith won't match @8thlight.com
            assert verify_domain("notanemail") is False
            assert verify_domain("missing-at-sign.com") is False
