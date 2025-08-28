import sys
import os
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientSession, ClientResponse

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.llm_service import LLMService
from config.settings import LLMSettings


class TestLLMService:
    """Tests for the LLMService class"""

    @pytest.fixture
    def llm_settings(self):
        """Create LLM settings for testing"""
        with patch.dict(os.environ, {
            "LLM_API_URL": "http://test-api.com",
            "LLM_API_KEY": "test-api-key",
            "LLM_MODEL": "test-model"
        }):
            return LLMSettings()

    @pytest.fixture
    def llm_service(self, llm_settings):
        """Create LLM service instance for testing"""
        return LLMService(llm_settings)

    @pytest.mark.asyncio
    async def test_init(self, llm_service):
        """Test LLMService initialization"""
        assert llm_service.api_url == "http://test-api.com"
        assert llm_service.api_key == "test-api-key"
        assert llm_service.model == "test-model"
        assert llm_service.session is None

    @pytest.mark.asyncio
    async def test_ensure_session_creates_new_session(self, llm_service):
        """Test that ensure_session creates a new session when none exists"""
        assert llm_service.session is None
        session = await llm_service.ensure_session()
        assert isinstance(session, ClientSession)
        assert llm_service.session is session

    @pytest.mark.asyncio
    async def test_ensure_session_reuses_existing_session(self, llm_service):
        """Test that ensure_session reuses existing session"""
        session1 = await llm_service.ensure_session()
        session2 = await llm_service.ensure_session()
        assert session1 is session2

    @pytest.mark.asyncio
    async def test_ensure_session_creates_new_when_closed(self, llm_service):
        """Test that ensure_session creates new session when current is closed"""
        session1 = await llm_service.ensure_session()
        await session1.close()
        session2 = await llm_service.ensure_session()
        assert session1 is not session2
        assert isinstance(session2, ClientSession)

    @pytest.mark.asyncio
    async def test_get_response_success(self, llm_service):
        """Test successful LLM API response"""
        messages = [{"role": "user", "content": "Hello"}]
        expected_response = "Hello! How can I help you?"
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock the response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "choices": [{"message": {"content": expected_response}}]
            })
            
            # Mock the context manager
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
            
            result = await llm_service.get_response(messages)
            
            assert result == expected_response

    @pytest.mark.asyncio
    async def test_get_response_with_user_id(self, llm_service):
        """Test LLM API response with user ID"""
        messages = [{"role": "user", "content": "Hello"}]
        user_id = "U12345"
        expected_response = "Hello! How can I help you?"
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock the response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "choices": [{"message": {"content": expected_response}}]
            })
            
            # Mock the context manager
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
            
            result = await llm_service.get_response(messages, user_id=user_id)
            
            assert result == expected_response
            
            # Verify the call was made with correct headers and payload
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            headers = call_args[1]['headers']
            payload = call_args[1]['json']
            
            assert headers["X-Auth-Token"] == f"slack:{user_id}"
            assert payload["metadata"]["X-Auth-Token"] == f"slack:{user_id}"
            assert payload["metadata"]["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_get_response_no_api_key(self):
        """Test get_response when API key is not set"""
        with patch.dict(os.environ, {
            "LLM_API_URL": "http://test-api.com",
            "LLM_API_KEY": "",
            "LLM_MODEL": "test-model"
        }):
            settings = LLMSettings()
            service = LLMService(settings)
        
            messages = [{"role": "user", "content": "Hello"}]
            result = await service.get_response(messages)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_get_response_api_error(self, llm_service):
        """Test LLM API error response"""
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock the error response
            mock_response = MagicMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            
            # Mock the context manager
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
            
            result = await llm_service.get_response(messages)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_get_response_network_error(self, llm_service):
        """Test network error during LLM API call"""
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock network error
            mock_post.side_effect = Exception("Network error")
            
            result = await llm_service.get_response(messages)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_get_response_payload_structure(self, llm_service):
        """Test that the payload sent to API has correct structure"""
        messages = [{"role": "user", "content": "Hello"}]
        user_id = "U12345"
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock the response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "choices": [{"message": {"content": "Response"}}]
            })
            
            # Mock the context manager
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
            
            await llm_service.get_response(messages, user_id=user_id)
            
            # Check the payload structure
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            
            assert payload["model"] == "test-model"
            assert payload["messages"] == messages
            assert payload["temperature"] == 0.7
            assert payload["max_tokens"] == 1000
            assert "metadata" in payload
            assert payload["metadata"]["X-Auth-Token"] == f"slack:{user_id}"
            assert payload["metadata"]["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_close_session(self, llm_service):
        """Test closing the HTTP session"""
        # Create a session first
        session = await llm_service.ensure_session()
        assert not session.closed
        
        # Close the service
        await llm_service.close()
        
        # Session should be closed
        assert session.closed

    @pytest.mark.asyncio
    async def test_close_no_session(self, llm_service):
        """Test closing when no session exists"""
        assert llm_service.session is None
        
        # Should not raise an error
        await llm_service.close()
        
        assert llm_service.session is None

    @pytest.mark.asyncio
    async def test_close_already_closed_session(self, llm_service):
        """Test closing when session is already closed"""
        session = await llm_service.ensure_session()
        await session.close()
        
        # Should not raise an error
        await llm_service.close()

    @pytest.mark.asyncio
    async def test_get_response_headers(self, llm_service):
        """Test that correct headers are sent to API"""
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock the response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "choices": [{"message": {"content": "Response"}}]
            })
            
            # Mock the context manager
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
            
            await llm_service.get_response(messages)
            
            # Check the headers
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            headers = call_args[1]['headers']
            
            assert headers["Authorization"] == "Bearer test-api-key"
            assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_get_response_url(self, llm_service):
        """Test that correct URL is used for API call"""
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock the response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "choices": [{"message": {"content": "Response"}}]
            })
            
            # Mock the context manager
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
            
            await llm_service.get_response(messages)
            
            # Check the URL
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            url = call_args[0][0]
            
            assert url == "http://test-api.com/chat/completions"