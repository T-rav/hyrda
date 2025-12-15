"""
Comprehensive tests for prompt service.

Tests prompt management, caching, and Langfuse integration.
"""

import pytest
from unittest.mock import Mock, patch

from config.settings import Settings
from services.prompt_service import (
    PromptService,
    get_prompt_service,
    initialize_prompt_service,
    DEFAULT_SYSTEM_MESSAGE,
)


class TestPromptServiceBasics:
    """Test basic prompt service functionality."""

    def test_prompt_service_can_be_imported(self):
        """Test that PromptService can be imported and instantiated."""
        settings = Settings()
        service = PromptService(settings)
        assert service is not None

    def test_prompt_service_initialization(self):
        """Test PromptService initialization with settings."""
        settings = Settings()
        service = PromptService(settings)

        assert service.settings == settings
        assert service.langfuse_settings == settings.langfuse
        assert service._cached_system_prompt is None
        assert service._prompt_cache == {}


class TestGetSystemPrompt:
    """Test getting system prompts."""

    def test_get_system_prompt_returns_default_when_langfuse_disabled(self):
        """Test that default prompt is returned when Langfuse is disabled."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = False
        service = PromptService(settings)

        prompt = service.get_system_prompt()
        assert prompt == DEFAULT_SYSTEM_MESSAGE
        assert "Insight Mesh" in prompt
        assert "AI CTO" in prompt

    def test_get_system_prompt_caches_result(self):
        """Test that system prompt is cached after first retrieval."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = False
        service = PromptService(settings)

        # First call
        prompt1 = service.get_system_prompt()
        assert service._cached_system_prompt == DEFAULT_SYSTEM_MESSAGE

        # Second call should use cache
        prompt2 = service.get_system_prompt()
        assert prompt1 == prompt2
        assert prompt2 == DEFAULT_SYSTEM_MESSAGE

    def test_get_system_prompt_force_refresh_bypasses_cache(self):
        """Test that force_refresh bypasses cache."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = False
        service = PromptService(settings)

        # First call
        service.get_system_prompt()
        service._cached_system_prompt = "OLD CACHE"

        # Force refresh should bypass old cache
        prompt = service.get_system_prompt(force_refresh=True)
        assert prompt == DEFAULT_SYSTEM_MESSAGE
        assert service._cached_system_prompt == DEFAULT_SYSTEM_MESSAGE

    @patch("services.prompt_service.get_langfuse_service")
    def test_get_system_prompt_from_langfuse_success(self, mock_get_langfuse):
        """Test successful retrieval from Langfuse."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = True
        settings.langfuse.system_prompt_template = "test-template"

        mock_langfuse = Mock()
        mock_langfuse.get_prompt_template.return_value = "Langfuse system prompt"
        mock_get_langfuse.return_value = mock_langfuse

        service = PromptService(settings)
        prompt = service.get_system_prompt()

        assert prompt == "Langfuse system prompt"
        assert service._cached_system_prompt == "Langfuse system prompt"
        mock_langfuse.get_prompt_template.assert_called_once_with(
            template_name="test-template", version=None
        )

    @patch("services.prompt_service.get_langfuse_service")
    def test_get_system_prompt_langfuse_not_available(self, mock_get_langfuse):
        """Test fallback when Langfuse service not available."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = True
        mock_get_langfuse.return_value = None

        service = PromptService(settings)
        prompt = service.get_system_prompt()

        assert prompt == DEFAULT_SYSTEM_MESSAGE

    @patch("services.prompt_service.get_langfuse_service")
    def test_get_system_prompt_langfuse_returns_none(self, mock_get_langfuse):
        """Test fallback when Langfuse returns None."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = True

        mock_langfuse = Mock()
        mock_langfuse.get_prompt_template.return_value = None
        mock_get_langfuse.return_value = mock_langfuse

        service = PromptService(settings)
        prompt = service.get_system_prompt()

        assert prompt == DEFAULT_SYSTEM_MESSAGE

    @patch("services.prompt_service.get_langfuse_service")
    def test_get_system_prompt_langfuse_error(self, mock_get_langfuse):
        """Test fallback when Langfuse raises error."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = True

        mock_langfuse = Mock()
        mock_langfuse.get_prompt_template.side_effect = Exception("Langfuse error")
        mock_get_langfuse.return_value = mock_langfuse

        service = PromptService(settings)
        prompt = service.get_system_prompt()

        assert prompt == DEFAULT_SYSTEM_MESSAGE


class TestGetCustomPrompt:
    """Test getting custom prompt templates."""

    @patch("services.prompt_service.get_langfuse_service")
    def test_get_custom_prompt_success(self, mock_get_langfuse):
        """Test successful custom prompt retrieval."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = True

        mock_langfuse = Mock()
        mock_langfuse.get_prompt_template.return_value = "Custom prompt text"
        mock_get_langfuse.return_value = mock_langfuse

        service = PromptService(settings)
        prompt = service.get_custom_prompt("custom-template")

        assert prompt == "Custom prompt text"
        mock_langfuse.get_prompt_template.assert_called_once_with("custom-template", None)

    @patch("services.prompt_service.get_langfuse_service")
    def test_get_custom_prompt_with_version(self, mock_get_langfuse):
        """Test custom prompt retrieval with specific version."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = True

        mock_langfuse = Mock()
        mock_langfuse.get_prompt_template.return_value = "Versioned prompt"
        mock_get_langfuse.return_value = mock_langfuse

        service = PromptService(settings)
        prompt = service.get_custom_prompt("custom-template", version="v2")

        assert prompt == "Versioned prompt"
        mock_langfuse.get_prompt_template.assert_called_once_with("custom-template", "v2")

    @patch("services.prompt_service.get_langfuse_service")
    def test_get_custom_prompt_caches_result(self, mock_get_langfuse):
        """Test that custom prompts are cached."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = True

        mock_langfuse = Mock()
        mock_langfuse.get_prompt_template.return_value = "Cached prompt"
        mock_get_langfuse.return_value = mock_langfuse

        service = PromptService(settings)

        # First call
        prompt1 = service.get_custom_prompt("test-template")
        # Second call should use cache
        prompt2 = service.get_custom_prompt("test-template")

        assert prompt1 == prompt2
        # Should only call Langfuse once
        mock_langfuse.get_prompt_template.assert_called_once()

    @patch("services.prompt_service.get_langfuse_service")
    def test_get_custom_prompt_with_fallback(self, mock_get_langfuse):
        """Test custom prompt with fallback when not found."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = True

        mock_langfuse = Mock()
        mock_langfuse.get_prompt_template.return_value = None
        mock_get_langfuse.return_value = mock_langfuse

        service = PromptService(settings)
        prompt = service.get_custom_prompt("missing-template", fallback="Fallback text")

        assert prompt == "Fallback text"

    @patch("services.prompt_service.get_langfuse_service")
    def test_get_custom_prompt_no_fallback(self, mock_get_langfuse):
        """Test custom prompt returns None when not found and no fallback."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = True

        mock_langfuse = Mock()
        mock_langfuse.get_prompt_template.return_value = None
        mock_get_langfuse.return_value = mock_langfuse

        service = PromptService(settings)
        prompt = service.get_custom_prompt("missing-template")

        assert prompt is None

    def test_get_custom_prompt_langfuse_disabled(self):
        """Test custom prompt when Langfuse is disabled."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = False

        service = PromptService(settings)
        prompt = service.get_custom_prompt("test-template", fallback="Fallback")

        assert prompt == "Fallback"


class TestCacheManagement:
    """Test prompt cache management."""

    def test_clear_cache(self):
        """Test clearing the prompt cache."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = False
        service = PromptService(settings)

        # Populate cache
        service.get_system_prompt()
        service._prompt_cache["test"] = "cached"

        assert service._cached_system_prompt is not None
        assert len(service._prompt_cache) > 0

        # Clear cache
        service.clear_cache()

        assert service._cached_system_prompt is None
        assert len(service._prompt_cache) == 0

    def test_cache_keys_with_version(self):
        """Test that cache keys include version."""
        settings = Settings()
        service = PromptService(settings)

        # Cache different versions
        service._prompt_cache["template:v1"] = "Version 1"
        service._prompt_cache["template:v2"] = "Version 2"
        service._prompt_cache["template:latest"] = "Latest"

        assert service._prompt_cache["template:v1"] == "Version 1"
        assert service._prompt_cache["template:v2"] == "Version 2"
        assert service._prompt_cache["template:latest"] == "Latest"


class TestGetPromptInfo:
    """Test getting prompt configuration info."""

    def test_get_prompt_info_langfuse_enabled(self):
        """Test getting prompt info when Langfuse enabled."""
        settings = Settings()
        settings.langfuse.enabled = True
        settings.langfuse.use_prompt_templates = True
        settings.langfuse.system_prompt_template = "main-prompt"
        settings.langfuse.prompt_template_version = "v1"

        service = PromptService(settings)
        info = service.get_prompt_info()

        assert info["langfuse_enabled"] is True
        assert info["use_prompt_templates"] is True
        assert info["system_prompt_template"] == "main-prompt"
        assert info["template_version"] == "v1"
        assert info["cached_system_prompt"] is False
        assert info["cache_size"] == 0

    def test_get_prompt_info_langfuse_disabled(self):
        """Test getting prompt info when Langfuse disabled."""
        settings = Settings()
        settings.langfuse.enabled = False

        service = PromptService(settings)
        info = service.get_prompt_info()

        assert info["langfuse_enabled"] is False

    def test_get_prompt_info_with_cache(self):
        """Test getting prompt info with cached data."""
        settings = Settings()
        settings.langfuse.use_prompt_templates = False
        service = PromptService(settings)

        # Populate cache
        service.get_system_prompt()
        service._prompt_cache["test1"] = "cached1"
        service._prompt_cache["test2"] = "cached2"

        info = service.get_prompt_info()

        assert info["cached_system_prompt"] is True
        assert info["cache_size"] == 2


class TestGlobalServiceManagement:
    """Test global prompt service instance management."""

    def test_initialize_prompt_service(self):
        """Test initializing global prompt service."""
        settings = Settings()
        service = initialize_prompt_service(settings)

        assert service is not None
        assert isinstance(service, PromptService)
        assert service.settings == settings

    def test_get_prompt_service_after_initialization(self):
        """Test getting global prompt service after initialization."""
        settings = Settings()
        initialized = initialize_prompt_service(settings)

        retrieved = get_prompt_service()

        assert retrieved is not None
        assert retrieved == initialized

    def test_get_prompt_service_before_initialization(self):
        """Test that get_prompt_service returns None before initialization."""
        # Reset global instance
        import services.prompt_service as ps

        ps._prompt_service = None

        result = get_prompt_service()
        assert result is None


class TestDefaultSystemMessage:
    """Test the default system message."""

    def test_default_system_message_content(self):
        """Test that default system message has expected content."""
        assert "Insight Mesh" in DEFAULT_SYSTEM_MESSAGE
        assert "AI CTO" in DEFAULT_SYSTEM_MESSAGE
        assert "knowledge base" in DEFAULT_SYSTEM_MESSAGE
        assert "documents" in DEFAULT_SYSTEM_MESSAGE
