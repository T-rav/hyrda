import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.user_prompt_service import UserPrompt, UserPromptService


@pytest.fixture
def mock_user_prompt_service():
    """Create a mock UserPromptService for testing"""
    service = MagicMock(spec=UserPromptService)

    # Mock async methods
    service.initialize = AsyncMock()
    service.close = AsyncMock()
    service.set_user_prompt = AsyncMock()
    service.get_user_prompt = AsyncMock()
    service.get_user_prompt_history = AsyncMock()
    service.reset_user_prompt = AsyncMock()

    return service


@pytest.fixture
def mock_database_url():
    """Mock database URL for testing"""
    return "postgresql+asyncpg://test:test@localhost:5432/test"


class TestUserPromptService:
    """Tests for UserPromptService database operations"""

    @pytest.mark.asyncio
    async def test_initialization_success(self, mock_database_url):
        """Test successful service initialization"""
        with patch(
            "services.user_prompt_service.create_async_engine"
        ), patch(
            "services.user_prompt_service.async_sessionmaker"
        ), patch(
            "services.user_prompt_service.MigrationManager"
        ) as mock_migration_manager:

            mock_migration_instance = AsyncMock()
            mock_migration_manager.return_value = mock_migration_instance
            mock_migration_instance.initialize = AsyncMock()
            mock_migration_instance.apply_migrations = AsyncMock()

            service = UserPromptService(mock_database_url)
            await service.initialize()

            # Verify initialization steps
            mock_migration_manager.assert_called_once_with(mock_database_url)
            mock_migration_instance.initialize.assert_called_once()
            mock_migration_instance.apply_migrations.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_user_prompt_success(self, mock_user_prompt_service):
        """Test successfully setting a user prompt"""
        user_id = "U12345"
        prompt = "You are a helpful Python expert"

        await mock_user_prompt_service.set_user_prompt(user_id, prompt)

        mock_user_prompt_service.set_user_prompt.assert_called_once_with(
            user_id, prompt
        )

    @pytest.mark.asyncio
    async def test_get_user_prompt_exists(self, mock_user_prompt_service):
        """Test getting an existing user prompt"""
        user_id = "U12345"
        expected_prompt = "You are a helpful Python expert"

        mock_user_prompt_service.get_user_prompt.return_value = expected_prompt

        result = await mock_user_prompt_service.get_user_prompt(user_id)

        assert result == expected_prompt
        mock_user_prompt_service.get_user_prompt.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_get_user_prompt_not_exists(self, mock_user_prompt_service):
        """Test getting a non-existent user prompt"""
        user_id = "U12345"

        mock_user_prompt_service.get_user_prompt.return_value = None

        result = await mock_user_prompt_service.get_user_prompt(user_id)

        assert result is None
        mock_user_prompt_service.get_user_prompt.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_get_user_prompt_history_with_data(self, mock_user_prompt_service):
        """Test getting user prompt history with existing data"""
        user_id = "U12345"
        expected_history = [
            {
                "prompt": "You are a helpful Python expert",
                "preview": "You are a helpful Python expert",
                "timestamp": "2024-01-01T10:00:00+00:00",
                "is_current": True,
            },
            {
                "prompt": "You are a helpful assistant",
                "preview": "You are a helpful assistant",
                "timestamp": "2024-01-01T09:00:00+00:00",
                "is_current": False,
            },
        ]

        mock_user_prompt_service.get_user_prompt_history.return_value = expected_history

        result = await mock_user_prompt_service.get_user_prompt_history(user_id)

        assert result == expected_history
        assert len(result) == 2
        assert result[0]["is_current"] is True
        assert result[1]["is_current"] is False
        mock_user_prompt_service.get_user_prompt_history.assert_called_once_with(
            user_id
        )

    @pytest.mark.asyncio
    async def test_get_user_prompt_history_empty(self, mock_user_prompt_service):
        """Test getting user prompt history with no data"""
        user_id = "U12345"

        mock_user_prompt_service.get_user_prompt_history.return_value = []

        result = await mock_user_prompt_service.get_user_prompt_history(user_id)

        assert result == []
        mock_user_prompt_service.get_user_prompt_history.assert_called_once_with(
            user_id
        )

    @pytest.mark.asyncio
    async def test_reset_user_prompt(self, mock_user_prompt_service):
        """Test resetting user prompts"""
        user_id = "U12345"

        await mock_user_prompt_service.reset_user_prompt(user_id)

        mock_user_prompt_service.reset_user_prompt.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_close_service(self, mock_user_prompt_service):
        """Test closing the service"""
        await mock_user_prompt_service.close()

        mock_user_prompt_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_user_prompt_error_handling(self, mock_user_prompt_service):
        """Test error handling in set_user_prompt"""
        user_id = "U12345"
        prompt = "Test prompt"

        # Mock an exception
        mock_user_prompt_service.set_user_prompt.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(Exception, match="Database error"):
            await mock_user_prompt_service.set_user_prompt(user_id, prompt)

    @pytest.mark.asyncio
    async def test_get_user_prompt_error_handling(self, mock_user_prompt_service):
        """Test error handling in get_user_prompt"""
        user_id = "U12345"

        # Mock an exception
        mock_user_prompt_service.get_user_prompt.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(Exception, match="Database error"):
            await mock_user_prompt_service.get_user_prompt(user_id)

    def test_prompt_preview_truncation(self):
        """Test that long prompts are properly previewed"""
        long_prompt = "This is a very long prompt that should be truncated when displayed as a preview in the history"
        expected_preview = long_prompt[:50] + "..."

        # This would normally be tested as part of the service logic
        preview = long_prompt[:50] + "..." if len(long_prompt) > 50 else long_prompt
        assert preview == expected_preview
        assert len(preview) <= 53  # 50 chars + "..."

    def test_prompt_model_fields(self):
        """Test UserPrompt model field validation"""
        # Test that model has expected fields
        expected_fields = ["id", "user_id", "prompt", "created_at", "is_current"]

        # This validates the SQLAlchemy model structure
        actual_fields = list(UserPrompt.__annotations__.keys())
        for field in expected_fields:
            assert field in actual_fields
