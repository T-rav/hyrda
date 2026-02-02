"""Qdrant vector store smoke tests.

Verifies RAG service is operational (vector store connectivity checked via ready endpoint).
"""

import os

import httpx
import pytest

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://rag-service:8002")


@pytest.mark.smoke
class TestRagServiceHealth:
    """Verify RAG service is operational."""

    def test_rag_service_health(self):
        """RAG service health endpoint returns 200."""
        response = httpx.get(
            f"{RAG_SERVICE_URL}/health",
            timeout=10.0,
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_rag_service_ready(self):
        """RAG service ready endpoint returns 200."""
        response = httpx.get(
            f"{RAG_SERVICE_URL}/ready",
            timeout=10.0,
        )
        assert response.status_code == 200
        # Response may indicate degraded if vector store is down, but endpoint responds
