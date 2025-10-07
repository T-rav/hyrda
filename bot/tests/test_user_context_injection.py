"""Tests for user context injection into system prompts."""

from unittest.mock import MagicMock, patch

import pytest

from handlers.message_handlers import get_user_system_prompt


@pytest.fixture
def mock_prompt_service():
    """Mock PromptService."""
    with patch("handlers.message_handlers.get_prompt_service") as mock:
        service = MagicMock()
        service.get_system_prompt.return_value = "I'm Insight Mesh, your AI assistant."
        mock.return_value = service
        yield service


@pytest.fixture
def mock_user_service():
    """Mock UserService."""
    with patch("services.user_service.get_user_service") as mock:
        service = MagicMock()
        mock.return_value = service
        yield service


def test_get_user_system_prompt_without_user_id(mock_prompt_service):
    """Test system prompt without user context."""
    prompt = get_user_system_prompt()

    assert prompt == "I'm Insight Mesh, your AI assistant."
    assert "Current User Context" not in prompt
    mock_prompt_service.get_system_prompt.assert_called_once()


def test_get_user_system_prompt_with_user_found(mock_prompt_service, mock_user_service):
    """Test system prompt with user context injected."""
    mock_user_service.get_user_info.return_value = {
        "slack_user_id": "U01234567",
        "name": "travis",
        "real_name": "Travis Frisinger",
        "email": "travis@example.com",
        "title": "Senior Engineer",
        "department": "Engineering",
        "is_admin": False,
        "is_bot": False,
    }

    prompt = get_user_system_prompt("U01234567")

    assert "I'm Insight Mesh, your AI assistant." in prompt
    assert "**Current User Context:**" in prompt
    assert "Name: Travis Frisinger" in prompt
    assert "Email: travis@example.com" in prompt
    assert "Title: Senior Engineer" in prompt
    assert "Department: Engineering" in prompt
    assert "personalize your responses" in prompt
    mock_user_service.get_user_info.assert_called_once_with("U01234567")


def test_get_user_system_prompt_with_user_not_found(
    mock_prompt_service, mock_user_service
):
    """Test system prompt when user not found in database."""
    mock_user_service.get_user_info.return_value = None

    prompt = get_user_system_prompt("U99999999")

    assert prompt == "I'm Insight Mesh, your AI assistant."
    assert "Current User Context" not in prompt
    mock_user_service.get_user_info.assert_called_once_with("U99999999")


def test_get_user_system_prompt_with_partial_user_data(
    mock_prompt_service, mock_user_service
):
    """Test system prompt with user who has no title/department."""
    mock_user_service.get_user_info.return_value = {
        "slack_user_id": "U01234567",
        "name": "john",
        "real_name": "John Doe",
        "email": "john@example.com",
        "title": None,
        "department": None,
        "is_admin": False,
        "is_bot": False,
    }

    prompt = get_user_system_prompt("U01234567")

    assert "**Current User Context:**" in prompt
    assert "Name: John Doe" in prompt
    assert "Email: john@example.com" in prompt
    # Should not include title/department lines if None
    assert "Title: None" not in prompt
    assert "Department: None" not in prompt


def test_get_user_system_prompt_with_user_service_error(
    mock_prompt_service, mock_user_service
):
    """Test system prompt when user service raises exception."""
    mock_user_service.get_user_info.side_effect = Exception("Database error")

    prompt = get_user_system_prompt("U01234567")

    # Should fallback to base prompt without crashing
    assert prompt == "I'm Insight Mesh, your AI assistant."
    assert "Current User Context" not in prompt


def test_get_user_system_prompt_without_prompt_service():
    """Test fallback when PromptService is not available."""
    with patch("handlers.message_handlers.get_prompt_service", return_value=None):
        prompt = get_user_system_prompt()

        assert "I'm Insight Mesh, your AI assistant" in prompt
        assert "knowledge base" in prompt


def test_get_user_system_prompt_uses_real_name_over_name(
    mock_prompt_service, mock_user_service
):
    """Test that real_name is preferred over name."""
    mock_user_service.get_user_info.return_value = {
        "slack_user_id": "U01234567",
        "name": "travis.frisinger",
        "real_name": "Travis Frisinger",
        "email": "travis@example.com",
        "title": None,
        "department": None,
        "is_admin": False,
        "is_bot": False,
    }

    prompt = get_user_system_prompt("U01234567")

    assert "Name: Travis Frisinger" in prompt
    assert "Name: travis.frisinger" not in prompt


def test_get_user_system_prompt_uses_name_when_no_real_name(
    mock_prompt_service, mock_user_service
):
    """Test that name is used when real_name is None."""
    mock_user_service.get_user_info.return_value = {
        "slack_user_id": "U01234567",
        "name": "travis",
        "real_name": None,
        "email": "travis@example.com",
        "title": None,
        "department": None,
        "is_admin": False,
        "is_bot": False,
    }

    prompt = get_user_system_prompt("U01234567")

    assert "Name: travis" in prompt
