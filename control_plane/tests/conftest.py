"""Pytest configuration - disable tracing during tests."""

import os
import sys
import tempfile
from pathlib import Path

# Create temporary SQLite database for ALL tests (shared across test modules)
security_db_fd, security_db_path = tempfile.mkstemp(suffix=".db")
os.close(security_db_fd)
os.chmod(security_db_path, 0o666)

# Set up SQLite BEFORE any imports (with check_same_thread=False for TestClient)
os.environ["SECURITY_DATABASE_URL"] = (
    f"sqlite:///{security_db_path}?check_same_thread=False"
)
os.environ["DATA_DATABASE_URL"] = (
    f"sqlite:///{security_db_path}?check_same_thread=False"
)
os.environ["OTEL_TRACES_ENABLED"] = "false"

# Add control_plane to path
control_plane_dir = Path(__file__).parent.parent
if str(control_plane_dir) not in sys.path:
    sys.path.insert(0, str(control_plane_dir))

# Import ALL models to register them with Base.metadata
from models.base import Base, get_db_session
from models import (
    ServiceAccount,
    User,
    UserIdentity,
    AgentMetadata,
    AgentPermission,
    PermissionGroup,
    UserGroup,
    AgentGroupPermission,
)

# Create tables ONCE for all tests
with get_db_session() as session:
    Base.metadata.create_all(session.bind)

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


@pytest.fixture(scope="session")
def app():
    """Get FastAPI app for testing (session scope - shared across all tests)."""
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
    """Create authenticated admin client with persistent auth overrides."""
    from fastapi import Request
    from utils.auth import require_admin as require_admin_auth
    from utils.permissions import require_admin as require_admin_permissions
    from dependencies.auth import get_current_user
    from dependencies.service_auth import verify_service_auth

    # Create mock admin user
    mock_admin_user = {
        "email": "admin@8thlight.com",
        "sub": "admin-sub-123",
        "name": "Test Admin",
        "is_admin": True,
    }

    # Mock all auth dependencies
    async def mock_require_admin_auth(request: Request):
        request.state.user = mock_admin_user
        return mock_admin_user

    async def mock_require_admin_permissions(request: Request):
        request.state.user = mock_admin_user
        return None

    async def mock_get_current_user():
        return mock_admin_user

    async def mock_verify_service_auth():
        return None

    # Override BOTH require_admin functions (from different modules)
    app.dependency_overrides[require_admin_auth] = mock_require_admin_auth
    app.dependency_overrides[require_admin_permissions] = mock_require_admin_permissions
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[verify_service_auth] = mock_verify_service_auth

    yield client

    # Don't clear overrides - they may be needed by other tests


@pytest.fixture(autouse=True)
def clean_database():
    """Clean database before each test."""
    with get_db_session() as session:
        # Delete in order to respect foreign key constraints
        session.query(AgentGroupPermission).delete()
        session.query(UserGroup).delete()
        session.query(AgentPermission).delete()
        session.query(PermissionGroup).delete()
        session.query(ServiceAccount).delete()
        session.query(UserIdentity).delete()
        session.query(User).delete()
        session.query(AgentMetadata).delete()
        session.commit()
    yield


@pytest.fixture
def service_account_builder():
    """Provides ServiceAccountBuilder for creating test service account payloads."""
    from tests.utils.builders.service_account_builder import ServiceAccountBuilder

    return ServiceAccountBuilder
