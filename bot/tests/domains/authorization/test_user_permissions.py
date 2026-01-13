"""Authorization domain tests - NO SKIPPING."""

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_control_plane_user_permissions_endpoint():
    """Test control plane user permissions endpoint."""
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get("https://localhost:6001/api/users", timeout=5.0)

        # 200 = success, 401/403 = auth required (both valid - service working)
        assert response.status_code in [200, 401, 403], (
            f"❌ Permissions endpoint failed: {response.status_code}\n"
            f"Control plane must be healthy!"
        )

        print(f"✅ Permissions endpoint working: {response.status_code}")
