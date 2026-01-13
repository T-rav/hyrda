"""Tests for authentication dependencies."""

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
