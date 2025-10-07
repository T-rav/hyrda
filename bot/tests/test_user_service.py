"""Tests for user service."""

from services.user_service import get_user_service


def test_get_user_service_singleton():
    """Test that get_user_service returns singleton instance."""
    service1 = get_user_service()
    service2 = get_user_service()
    assert service1 is service2
