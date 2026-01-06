"""Pytest configuration - disable tracing during tests."""
import os
os.environ["OTEL_TRACES_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture(autouse=True)
def reset_prometheus_registry():
    """Reset Prometheus registry between tests to avoid duplicate metric errors."""
    from prometheus_client import REGISTRY

    # Collect all collectors before test
    collectors_before = list(REGISTRY._collector_to_names.keys())

    yield

    # Clean up any new collectors added during test
    collectors_after = list(REGISTRY._collector_to_names.keys())
    for collector in collectors_after:
        if collector not in collectors_before:
            try:
                REGISTRY.unregister(collector)
            except Exception:
                pass  # Already unregistered or not in registry


@pytest.fixture(scope="module")
def app():
    """Get FastAPI app for testing."""
    from app import create_app
    return create_app()


@pytest.fixture
def mock_oauth_env():
    """Mock OAuth environment variables."""
    with patch.dict(
        os.environ,
        {
            "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
            "ALLOWED_EMAIL_DOMAIN": "@8thlight.com",
        },
        clear=False,
    ):
        yield


@pytest.fixture
def client(app, mock_oauth_env):
    """Create test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client, app):
    """Create authenticated admin client."""
    from fastapi import Request
    from utils.auth import require_admin

    mock_admin_user = {
        "email": "admin@8thlight.com",
        "sub": "admin-sub-123",
        "name": "Test Admin",
        "is_admin": True,
    }

    async def mock_require_admin(request: Request):
        request.state.user = mock_admin_user
        return mock_admin_user

    app.dependency_overrides[require_admin] = mock_require_admin
    yield client
    app.dependency_overrides.clear()
