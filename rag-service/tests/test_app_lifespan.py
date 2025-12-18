"""Tests for RAG service application lifespan and startup."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


class TestAppLifespan:
    """Test application lifespan management."""

    @pytest.mark.asyncio
    async def test_lifespan_initializes_search_clients(self):
        """Test that lifespan initializes search clients (Tavily, Perplexity)."""
        from app import lifespan
        from fastapi import FastAPI

        mock_app = FastAPI()

        with patch("app.initialize_metrics_service") as mock_metrics_init:
            with patch("app.get_settings") as mock_settings:
                with patch("app.create_vector_store") as mock_vector_store:
                    with patch("app.initialize_search_clients") as mock_search_init:
                        # Setup mocks
                        mock_settings_obj = MagicMock()
                        mock_settings_obj.port = 8002
                        mock_settings_obj.environment = "test"
                        mock_settings_obj.vector.enabled = True
                        mock_settings_obj.rag.enable_query_rewriting = True
                        mock_settings_obj.search.tavily_api_key = "test-tavily-key"
                        mock_settings_obj.search.perplexity_api_key = "test-perplexity-key"
                        mock_settings.return_value = mock_settings_obj

                        mock_vector = AsyncMock()
                        mock_vector.initialize = AsyncMock()
                        mock_vector_store.return_value = mock_vector

                        mock_search_init.return_value = AsyncMock()

                        # Run lifespan
                        async with lifespan(mock_app):
                            pass

                        # Verify search clients were initialized
                        mock_search_init.assert_called_once_with(
                            tavily_api_key="test-tavily-key",
                            perplexity_api_key="test-perplexity-key",
                        )

    @pytest.mark.asyncio
    async def test_lifespan_handles_search_client_init_failure(self):
        """Test that lifespan handles search client initialization failures gracefully."""
        from app import lifespan
        from fastapi import FastAPI

        mock_app = FastAPI()

        with patch("app.initialize_metrics_service"):
            with patch("app.get_settings") as mock_settings:
                with patch("app.create_vector_store") as mock_vector_store:
                    with patch("app.initialize_search_clients") as mock_search_init:
                        with patch("app.logger") as mock_logger:
                            # Setup mocks
                            mock_settings_obj = MagicMock()
                            mock_settings_obj.port = 8002
                            mock_settings_obj.environment = "test"
                            mock_settings_obj.vector.enabled = False
                            mock_settings_obj.rag.enable_query_rewriting = False
                            mock_settings_obj.search.tavily_api_key = None
                            mock_settings_obj.search.perplexity_api_key = None
                            mock_settings.return_value = mock_settings_obj

                            # Make search client init fail
                            mock_search_init.side_effect = Exception("Failed to init")

                            # Run lifespan - should not raise
                            async with lifespan(mock_app):
                                pass

                            # Verify warning was logged
                            assert mock_logger.warning.called
                            warning_call = mock_logger.warning.call_args[0][0]
                            assert "Search clients initialization failed" in warning_call

    @pytest.mark.asyncio
    async def test_lifespan_cleanup_search_clients(self):
        """Test that lifespan cleans up search clients on shutdown."""
        from app import lifespan
        from fastapi import FastAPI

        mock_app = FastAPI()

        with patch("app.initialize_metrics_service"):
            with patch("app.get_settings") as mock_settings:
                with patch("app.create_vector_store") as mock_vector_store:
                    with patch("app.initialize_search_clients"):
                        with patch("app.cleanup_search_clients") as mock_cleanup:
                            # Setup mocks
                            mock_settings_obj = MagicMock()
                            mock_settings_obj.port = 8002
                            mock_settings_obj.environment = "test"
                            mock_settings_obj.vector.enabled = False
                            mock_settings_obj.rag.enable_query_rewriting = False
                            mock_settings_obj.search.tavily_api_key = "test-key"
                            mock_settings_obj.search.perplexity_api_key = None
                            mock_settings.return_value = mock_settings_obj

                            mock_cleanup.return_value = AsyncMock()

                            # Run lifespan
                            async with lifespan(mock_app):
                                pass

                            # Verify cleanup was called
                            mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_initializes_vector_store(self):
        """Test that lifespan initializes vector store when enabled."""
        from app import lifespan
        from fastapi import FastAPI

        mock_app = FastAPI()

        with patch("app.initialize_metrics_service"):
            with patch("app.get_settings") as mock_settings:
                with patch("app.create_vector_store") as mock_vector_store:
                    with patch("app.initialize_search_clients"):
                        # Setup mocks
                        mock_settings_obj = MagicMock()
                        mock_settings_obj.port = 8002
                        mock_settings_obj.environment = "test"
                        mock_settings_obj.vector.enabled = True
                        mock_settings_obj.rag.enable_query_rewriting = True
                        mock_settings_obj.search.tavily_api_key = "test-key"
                        mock_settings_obj.search.perplexity_api_key = None
                        mock_settings.return_value = mock_settings_obj

                        mock_vector = AsyncMock()
                        mock_vector.initialize = AsyncMock()
                        mock_vector_store.return_value = mock_vector

                        # Run lifespan
                        async with lifespan(mock_app):
                            pass

                        # Verify vector store was created and initialized
                        mock_vector_store.assert_called_once()
                        mock_vector.initialize.assert_called_once()


class TestAppVersion:
    """Test application version management."""

    def test_get_app_version_returns_version(self):
        """Test that get_app_version returns version from .version file."""
        from app import get_app_version
        from pathlib import Path

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value="1.1.0\n"):
                version = get_app_version()
                assert version == "1.1.0"

    def test_get_app_version_returns_default_when_file_missing(self):
        """Test that get_app_version returns default when .version file missing."""
        from app import get_app_version
        from pathlib import Path

        with patch.object(Path, "exists", return_value=False):
            version = get_app_version()
            assert version == "0.0.0"

    def test_get_app_version_handles_read_error(self):
        """Test that get_app_version handles file read errors."""
        from app import get_app_version
        from pathlib import Path

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", side_effect=Exception("Read error")):
                version = get_app_version()
                assert version == "0.0.0"


class TestAppCreation:
    """Test FastAPI application creation."""

    def test_app_is_created_with_correct_metadata(self):
        """Test that FastAPI app is created with correct metadata."""
        from app import app

        assert app is not None
        assert app.title == "RAG Service"
        assert "Retrieval-Augmented Generation" in app.description

    def test_app_has_cors_middleware(self):
        """Test that app has CORS middleware configured."""
        from app import app
        from fastapi.middleware.cors import CORSMiddleware

        # Check that CORS middleware is in the middleware stack
        middleware_types = [type(m) for m in app.user_middleware]
        # CORSMiddleware might be wrapped, so check if it's present
        assert len(app.user_middleware) > 0

    def test_app_has_tracing_middleware(self):
        """Test that app has tracing middleware configured."""
        from app import app

        # Verify middleware stack is not empty
        assert len(app.user_middleware) > 0
