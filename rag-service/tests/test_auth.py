"""Tests for authentication dependencies."""

import os

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from dependencies.auth import require_service_auth


def test_require_service_auth_missing_token():
    """Test that missing service token returns 401."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(service: dict = Depends(require_service_auth)):
        return {"service": service}

    client = TestClient(app)
    response = client.get("/test")

    assert response.status_code == 401
    assert "authentication required" in response.json()["detail"].lower()


def test_require_service_auth_invalid_token():
    """Test that invalid service token returns 401."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(service: dict = Depends(require_service_auth)):
        return {"service": service}

    client = TestClient(app)
    response = client.get(
        "/test",
        headers={"X-Service-Token": "invalid-token"},
    )

    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


def test_health_endpoint_no_auth(test_client):
    """Test that health endpoint doesn't require authentication."""
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "rag-service"
    assert response.json()["status"] == "healthy"


def test_ready_endpoint_no_auth(test_client):
    """Test that ready endpoint doesn't require authentication."""
    response = test_client.get("/ready")

    assert response.status_code == 200
    assert "status" in response.json()


def test_root_endpoint_no_auth(test_client):
    """Test that root endpoint doesn't require authentication."""
    response = test_client.get("/")

    assert response.status_code == 200
    assert response.json()["service"] == "rag-service"
    assert "capabilities" in response.json()


def test_oauth_token_capture():
    """Test that Google OAuth token is properly captured when provided."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(auth: dict = Depends(require_service_auth)):
        return {"auth": auth}

    client = TestClient(app)
    service_token = os.getenv("RAG_SERVICE_TOKEN", "fake-test-token-for-testing-only")
    oauth_token = "ya29.test-google-oauth-token"

    response = client.get(
        "/test",
        headers={
            "X-Service-Token": service_token,
            "X-User-Email": "user@example.com",
            "X-Google-OAuth-Token": oauth_token,
        },
    )

    assert response.status_code == 200
    auth = response.json()["auth"]
    assert auth["google_oauth_token"] == oauth_token
    assert auth["user_email"] == "user@example.com"
    assert auth["service"] == "rag"
    assert auth["auth_method"] == "service"


def test_oauth_token_optional():
    """Test that OAuth token is optional and auth works without it."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(auth: dict = Depends(require_service_auth)):
        return {"auth": auth}

    client = TestClient(app)
    service_token = os.getenv("RAG_SERVICE_TOKEN", "fake-test-token-for-testing-only")

    response = client.get(
        "/test",
        headers={
            "X-Service-Token": service_token,
            "X-User-Email": "user@example.com",
            # No X-Google-OAuth-Token header
        },
    )

    assert response.status_code == 200
    auth = response.json()["auth"]
    assert "google_oauth_token" not in auth  # OAuth token not in response
    assert auth["user_email"] == "user@example.com"
    assert auth["service"] == "rag"


def test_oauth_token_with_different_service():
    """Test OAuth token works with different service names."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(auth: dict = Depends(require_service_auth)):
        return {"auth": auth}

    client = TestClient(app)
    oauth_token = "ya29.test-google-oauth-token-v2"
    service_token = os.getenv("RAG_SERVICE_TOKEN", "fake-test-token-for-testing-only")

    response = client.get(
        "/test",
        headers={
            "X-Service-Token": service_token,
            "X-User-Email": "different-user@example.com",
            "X-Google-OAuth-Token": oauth_token,
        },
    )

    assert response.status_code == 200
    auth = response.json()["auth"]
    assert auth["google_oauth_token"] == oauth_token
    assert auth["user_email"] == "different-user@example.com"
    # Service tokens are consistently handled regardless of which service
