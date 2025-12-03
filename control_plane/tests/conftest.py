"""Shared fixtures for control_plane tests.

This file provides common fixtures and test utilities available to all test files.
Following the pattern established in bot/tests/conftest.py
"""

import pytest
from unittest.mock import AsyncMock, Mock
from fastapi.testclient import TestClient


# ===========================
# Application Fixtures
# ===========================


@pytest.fixture
def test_client():
    """Provide FastAPI test client.

    Returns:
        TestClient: FastAPI test client for API endpoint testing
    """
    from api import create_app

    app = create_app()
    return TestClient(app)


# ===========================
# Authentication Fixtures
# ===========================


@pytest.fixture
def mock_auth_service():
    """Provide mocked authentication service.

    Returns:
        Mock: Auth service with verify_token, authenticate methods
    """
    service = Mock()
    service.verify_token.return_value = {"user_id": "U123", "email": "test@example.com"}
    service.authenticate.return_value = True
    service.generate_token.return_value = "test_token_12345"
    return service


@pytest.fixture
def authenticated_headers():
    """Provide headers with valid auth token.

    Returns:
        dict: HTTP headers with Authorization token

    Example:
        def test_protected_endpoint(test_client, authenticated_headers):
            response = test_client.get("/api/users", headers=authenticated_headers)
            assert response.status_code == 200
    """
    return {"Authorization": "Bearer test_token_12345"}


@pytest.fixture
def mock_current_user():
    """Provide mock current user data.

    Returns:
        dict: Current user object
    """
    return {
        "user_id": "U123",
        "email": "test@example.com",
        "name": "Test User",
        "is_admin": False,
        "is_active": True,
    }


# ===========================
# User Provider Fixtures
# ===========================


@pytest.fixture
def mock_slack_user_provider():
    """Provide mocked Slack user provider.

    Returns:
        AsyncMock: Slack provider with fetch_users, sync_users methods
    """
    provider = AsyncMock()
    provider.fetch_users.return_value = [
        {
            "id": "U123",
            "name": "test.user",
            "email": "test.user@example.com",
            "is_admin": False,
        }
    ]
    provider.sync_users.return_value = {"synced": 1, "failed": 0}
    return provider


@pytest.fixture
def mock_google_user_provider():
    """Provide mocked Google Workspace user provider.

    Returns:
        AsyncMock: Google provider with fetch_users, sync_users methods
    """
    provider = AsyncMock()
    provider.fetch_users.return_value = [
        {
            "id": "google_123",
            "name": "test.user",
            "email": "test.user@company.com",
            "is_admin": False,
        }
    ]
    provider.sync_users.return_value = {"synced": 1, "failed": 0}
    return provider


# ===========================
# Sample User Data Fixtures
# ===========================


@pytest.fixture
def sample_slack_users():
    """Provide sample Slack users data for testing.

    Returns:
        list: List of Slack user dictionaries
    """
    return [
        {
            "id": "U123",
            "name": "test.user",
            "email": "test.user@example.com",
            "is_admin": False,
            "is_owner": False,
            "profile": {
                "email": "test.user@example.com",
                "real_name": "Test User",
            },
        },
        {
            "id": "U456",
            "name": "admin.user",
            "email": "admin.user@example.com",
            "is_admin": True,
            "is_owner": False,
            "profile": {
                "email": "admin.user@example.com",
                "real_name": "Admin User",
            },
        },
    ]


@pytest.fixture
def sample_google_users():
    """Provide sample Google Workspace users for testing.

    Returns:
        list: List of Google user dictionaries
    """
    return [
        {
            "id": "google_123",
            "primaryEmail": "test.user@company.com",
            "name": {"fullName": "Test User"},
            "isAdmin": False,
            "suspended": False,
        },
        {
            "id": "google_456",
            "primaryEmail": "admin.user@company.com",
            "name": {"fullName": "Admin User"},
            "isAdmin": True,
            "suspended": False,
        },
    ]


# ===========================
# Database Fixtures
# ===========================


@pytest.fixture
def mock_database():
    """Provide mocked database connection.

    Returns:
        AsyncMock: Database with execute, fetch_all, fetch_one methods
    """
    db = AsyncMock()
    db.execute.return_value = None
    db.fetch_all.return_value = []
    db.fetch_one.return_value = None
    return db


# ===========================
# Event Loop Fixtures
# ===========================


@pytest.fixture(scope="session")
def event_loop():
    """Provide event loop for async tests.

    Returns:
        asyncio.AbstractEventLoop: Event loop for the test session
    """
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
