"""Simple tests for permissions constants and basic functions."""

from utils.permissions import PERMISSION_TIERS, PermissionTier


class TestPermissionTierConstants:
    """Test permission tier constants."""

    def test_permission_tier_values(self):
        """Test that permission tier constants have expected values."""
        assert PermissionTier.ADMIN == "admin"
        assert PermissionTier.POWER_USER == "power_user"
        assert PermissionTier.READ_ONLY == "read_only"
        assert PermissionTier.USER == "user"

    def test_permission_tiers_mapping(self):
        """Test that PERMISSION_TIERS mapping is defined correctly."""
        assert "manage_groups" in PERMISSION_TIERS
        assert "manage_agents" in PERMISSION_TIERS
        assert "manage_users" in PERMISSION_TIERS
        assert "view_groups" in PERMISSION_TIERS
        assert "view_agents" in PERMISSION_TIERS

        # Admin should have access to manage permissions
        assert PermissionTier.ADMIN in PERMISSION_TIERS["manage_groups"]
        assert PermissionTier.ADMIN in PERMISSION_TIERS["manage_agents"]
        assert PermissionTier.ADMIN in PERMISSION_TIERS["manage_users"]

        # View permissions should include multiple tiers
        assert PermissionTier.ADMIN in PERMISSION_TIERS["view_groups"]
        assert PermissionTier.POWER_USER in PERMISSION_TIERS["view_groups"]
        assert PermissionTier.READ_ONLY in PERMISSION_TIERS["view_groups"]

        assert PermissionTier.ADMIN in PERMISSION_TIERS["view_agents"]
        assert PermissionTier.POWER_USER in PERMISSION_TIERS["view_agents"]
        assert PermissionTier.READ_ONLY in PERMISSION_TIERS["view_agents"]
