"""Authentication domain tests - NO SKIPPING."""

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_control_plane_oauth_login():
    """Test control plane OAuth login endpoint."""
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get("http://localhost:6001/auth/login", timeout=5.0)

        assert response.status_code in [200, 302], (
            f"❌ OAuth login failed: {response.status_code}\n"
            f"Control plane must be healthy!"
        )

        print(f"✅ OAuth login endpoint working: {response.status_code}")


async def test_control_plane_health():
    """Test control plane health endpoint."""
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get("http://localhost:6001/health", timeout=5.0)

        assert response.status_code == 200, (
            f"❌ Control plane unhealthy: {response.status_code}"
        )

        print("✅ Control plane is healthy")
