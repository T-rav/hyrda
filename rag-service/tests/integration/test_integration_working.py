"""
Working Integration Tests

These integration tests actually pass and test real functionality:
- Health endpoints
- Context building with real components
- Quality validation

Mark: integration (run separately from unit tests)
"""

import pytest
from fastapi.testclient import TestClient

from app import app
from services.context_builder import ContextBuilder

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    """Create test client for API testing."""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health and readiness endpoints."""

    def test_health_endpoint(self, client):
        """Test /health endpoint returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data

    def test_ready_endpoint(self, client):
        """Test /ready endpoint checks service readiness."""
        response = client.get("/ready")

        # Should return 200 or 503 depending on readiness
        assert response.status_code in [200, 503]

    def test_root_endpoint(self, client):
        """Test root endpoint returns service info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert data["service"] == "rag-service"


class TestContextBuilding:
    """Test context building from retrieved chunks."""

    def test_build_context_with_retrieved_chunks(self):
        """Test building context from retrieved chunks."""
        builder = ContextBuilder()

        chunks = [
            {
                "content": "Python is a high-level programming language.",
                "similarity": 0.9,
                "metadata": {"file_name": "python_intro.pdf", "source": "google_drive"},
            },
            {
                "content": "Python supports multiple programming paradigms.",
                "similarity": 0.85,
                "metadata": {"file_name": "python_features.pdf", "source": "google_drive"},
            },
        ]

        query = "What is Python?"
        history = []
        system_msg = "You are a helpful assistant."

        final_system, messages = builder.build_rag_prompt(query, chunks, history, system_msg)

        assert "Python is a high-level programming language" in final_system
        assert "KNOWLEDGE BASE" in final_system
        assert len(messages) == 1
        assert messages[0]["content"] == query

    def test_build_context_with_uploaded_document(self):
        """Test building context with uploaded document."""
        builder = ContextBuilder()

        chunks = [
            {
                "content": "Uploaded document content here.",
                "similarity": 1.0,
                "metadata": {
                    "file_name": "upload.pdf",
                    "source": "uploaded_document",
                },
            },
            {
                "content": "Retrieved knowledge base content.",
                "similarity": 0.8,
                "metadata": {"file_name": "kb.pdf", "source": "google_drive"},
            },
        ]

        query = "Analyze this document"
        final_system, messages = builder.build_rag_prompt(query, chunks, [], "System message")

        assert "UPLOADED DOCUMENT" in final_system
        assert "KNOWLEDGE BASE" in final_system
        assert "Primary user content for analysis" in final_system

    def test_validate_context_quality_high(self):
        """Test context quality validation for high-quality results."""
        builder = ContextBuilder()

        chunks = [
            {
                "content": "High quality content",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf"},
            },
            {
                "content": "More high quality content",
                "similarity": 0.85,
                "metadata": {"file_name": "doc2.pdf"},
            },
        ]

        quality = builder.validate_context_quality(chunks, min_similarity=0.5)

        assert quality["quality_score"] > 0.7
        assert quality["high_quality_chunks"] == 2
        assert quality["avg_similarity"] > 0.8
        assert len(quality["warnings"]) == 0

    def test_validate_context_quality_low(self):
        """Test context quality validation for low-quality results."""
        builder = ContextBuilder()

        chunks = [
            {
                "content": "Low quality content",
                "similarity": 0.3,
                "metadata": {"file_name": "doc.pdf"},
            }
        ]

        quality = builder.validate_context_quality(chunks, min_similarity=0.5)

        assert quality["high_quality_chunks"] == 0
        assert len(quality["warnings"]) > 0


class TestCitationService:
    """Test citation service integration."""

    def test_citation_formatting_integration(self):
        """Test end-to-end citation formatting."""
        from services.citation_service import CitationService

        service = CitationService()

        chunks = [
            {
                "content": "Document content",
                "similarity": 0.9,
                "metadata": {
                    "file_name": "report.pdf",
                    "source": "google_drive",
                    "web_view_link": "https://example.com/doc",
                },
            }
        ]

        response = "This is the answer based on the document."
        result = service.add_source_citations(response, chunks)

        assert "📚 Sources:" in result
        assert "report" in result
        assert "90.0%" in result or "90%" in result
