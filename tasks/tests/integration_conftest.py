"""Integration test fixtures for tasks service with REAL services.

Provides production-quality fixtures that:
1. Connect to REAL control-plane service (not mocks)
2. Generate REAL JWT tokens for authentication
3. Make REAL HTTP requests to test auth flow
"""

import os
from datetime import datetime, timedelta

import httpx
import jwt
import pytest


@pytest.fixture(scope="function", autouse=True)
def set_control_plane_url_for_tests(monkeypatch):
    """Set CONTROL_PLANE_INTERNAL_URL for all integration tests."""
    # This ensures dependencies/auth.py uses localhost instead of Docker hostname
    monkeypatch.setenv("CONTROL_PLANE_INTERNAL_URL", "https://localhost:6001")


@pytest.fixture
def control_plane_url() -> str:
    """Control plane service URL for integration testing."""
    return os.getenv("CONTROL_PLANE_URL", "https://localhost:6001")


@pytest.fixture
def generate_real_jwt():
    """Factory to generate valid JWT tokens for testing."""

    def _generate(user_data: dict) -> str:
        """Generate a valid JWT token matching control-plane expectations."""
        secret = os.getenv(
            "JWT_SECRET_KEY",
            "d70c7728c068afeb86a928b2ed3d4210500c2dc095dfba1820a663bf36dc1b57",
        )

        payload = {
            "user_id": user_data.get("user_id", "U123"),
            "email": user_data["email"],
            "is_admin": user_data.get("is_admin", False),
            "name": user_data.get("real_name", "Test User"),
            "iss": "insightmesh",  # Must match JWT_ISSUER
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
        }

        return jwt.encode(payload, secret, algorithm="HS256")

    return _generate


@pytest.fixture
async def integration_http_client() -> httpx.AsyncClient:
    """HTTP client for integration tests with real services."""
    async with httpx.AsyncClient(
        timeout=30.0, follow_redirects=False, verify=False
    ) as client:
        yield client


@pytest.fixture
def valid_user_data() -> dict:
    """Valid test user data (8thlight.com domain)."""
    return {
        "user_id": "U123TEST",
        "email": "testuser@8thlight.com",
        "real_name": "Test User",
        "is_admin": False,
    }


@pytest.fixture
def invalid_domain_user_data() -> dict:
    """Invalid test user data (wrong domain)."""
    return {
        "user_id": "U456EVIL",
        "email": "attacker@evil.com",
        "real_name": "Evil User",
        "is_admin": False,
    }


@pytest.fixture
def admin_user_data() -> dict:
    """Admin test user data."""
    return {
        "user_id": "U08QVTBAWH0",
        "email": "tmfrisinger@gmail.com",
        "real_name": "Test Admin",
        "is_admin": True,
    }


@pytest.fixture
async def authenticated_request_headers(generate_real_jwt, valid_user_data) -> dict:
    """Generate authenticated request headers with real JWT."""
    token = generate_real_jwt(valid_user_data)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def check_control_plane_available(control_plane_url) -> bool:
    """Check if control-plane service is available for integration tests."""
    try:
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            response = await client.get(f"{control_plane_url}/health")
            return response.status_code == 200
    except Exception:
        return False
