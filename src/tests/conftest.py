import pytest
import os
from unittest.mock import patch, MagicMock

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment with mock credentials and settings"""
    
    # Mock environment variables for all tests
    test_env = {
        # Slack settings
        "SLACK_BOT_TOKEN": "xoxb-test-bot-token",
        "SLACK_APP_TOKEN": "xapp-test-app-token", 
        "SLACK_BOT_ID": "B1234567890",
        
        # LLM settings
        "LLM_API_URL": "http://localhost:9091",
        "LLM_API_KEY": "test-api-key",
        "LLM_MODEL": "gpt-4o-mini",
        
        # Agent settings
        "AGENT_ENABLED": "true",
        
        # General settings
        "DEBUG": "false",
        "LOG_LEVEL": "INFO"
    }
    
    with patch.dict(os.environ, test_env, clear=False):
        yield

@pytest.fixture
def mock_slack_client():
    """Mock Slack client for tests"""
    mock_client = MagicMock()
    mock_client.chat_postMessage.return_value = {"ok": True, "ts": "1234567890.123456"}
    mock_client.conversations_history.return_value = {
        "ok": True,
        "messages": []
    }
    mock_client.users_info.return_value = {
        "ok": True,
        "user": {
            "id": "U1234567890",
            "name": "testuser",
            "real_name": "Test User"
        }
    }
    return mock_client

@pytest.fixture
def mock_llm_response():
    """Mock LLM response for tests"""
    return {
        "choices": [{
            "message": {
                "content": "This is a test response from the LLM."
            }
        }]
    }

@pytest.fixture
def sample_slack_event():
    """Sample Slack event for testing"""
    return {
        "type": "message",
        "user": "U1234567890",
        "text": "Hello bot!",
        "channel": "C1234567890",
        "ts": "1234567890.123456",
        "team": "T1234567890"
    }

@pytest.fixture
def sample_slack_message():
    """Sample Slack message for testing"""
    return {
        "channel": "C1234567890",
        "user": "U1234567890", 
        "text": "Test message",
        "ts": "1234567890.123456",
        "team": "T1234567890",
        "thread_ts": None
    } 