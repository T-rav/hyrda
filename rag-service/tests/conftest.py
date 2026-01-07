"""Pytest configuration - disable tracing during tests."""
import json
import os
import time

# Set environment variables BEFORE imports (critical for jwt_auth module initialization)
os.environ["OTEL_TRACES_ENABLED"] = "false"
os.environ["LLM_API_KEY"] = "test-api-key-for-testing"
if not os.getenv("RAG_SERVICE_TOKEN"):
    os.environ["RAG_SERVICE_TOKEN"] = "test-rag-service-token-172b784535a9c8548b9a6f62c257e6410db2cb022e80a4fe31e7b6c3b0f06128"  # ggignore

# Now safe to import after environment is configured
import pytest
from fastapi.testclient import TestClient

# Import after environment setup
import sys
from unittest.mock import patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.utils.request_signing import generate_signature


@pytest.fixture
def test_client():
    """Create FastAPI test client for integration tests."""
    from app import app
    return TestClient(app)


@pytest.fixture
def client():
    """Create FastAPI test client (alias for test_client)."""
    from app import app
    return TestClient(app)


@pytest.fixture
def unauth_client():
    """Create unauthenticated test client."""
    from app import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Provide authentication headers for GET requests (no HMAC required)."""
    return {"X-Service-Token": os.getenv("RAG_SERVICE_TOKEN", "test-rag-service-token")}


def generate_signed_headers(payload: dict) -> dict:
    """Generate properly signed headers for POST requests with HMAC.

    Args:
        payload: Request body as dict

    Returns:
        Headers dict with X-Service-Token, X-Request-Timestamp, X-Request-Signature, and X-User-Email
    """
    service_token = os.getenv("RAG_SERVICE_TOKEN", "test-rag-service-token")
    timestamp = str(int(time.time()))
    # Use same JSON encoding as FastAPI TestClient (no spaces, sorted keys)
    body_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)

    signature = generate_signature(service_token, body_json, timestamp)

    return {
        "X-Service-Token": service_token,
        "X-Request-Timestamp": timestamp,
        "X-Request-Signature": signature,
        "X-User-Email": "test@example.com",  # Required by auth middleware
    }


@pytest.fixture
def signed_headers():
    """Provide helper function to generate signed headers for POST requests."""
    return generate_signed_headers


@pytest.fixture(autouse=True)
def mock_signature_verification():
    """Mock HMAC signature verification to always pass for tests."""
    with patch("shared.utils.request_signing.verify_signature") as mock_verify:
        # Return (True, None) to indicate signature is valid
        mock_verify.return_value = (True, None)
        yield mock_verify


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
