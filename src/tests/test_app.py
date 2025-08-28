import sys
import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, maintain_presence, run, main
from config.settings import Settings
from services.llm_service import LLMService
from services.slack_service import SlackService


class TestApp:
    """Tests for the main app functionality"""

    @pytest.mark.asyncio
    async def test_create_app(self):
        """Test app creation and configuration"""
        with patch.dict(os.environ, {
            "SLACK_BOT_TOKEN": "xoxb-test-token",
            "SLACK_APP_TOKEN": "xapp-test-token", 
            "SLACK_BOT_ID": "B123",
            "LLM_API_URL": "http://test-api.com",
            "LLM_API_KEY": "test-api-key"
        }):
            with patch('app.AsyncApp') as mock_app_class, \
                 patch('app.LLMService') as mock_llm_service_class, \
                 patch('app.SlackService') as mock_slack_service_class, \
                 patch('app.register_handlers') as mock_register_handlers, \
                 patch('app.asyncio.create_task') as mock_create_task:
                
                # Mock AsyncApp
                mock_app = MagicMock()
                mock_app.client = MagicMock()
                mock_app_class.return_value = mock_app
                
                # Mock services
                mock_llm_service = MagicMock()
                mock_slack_service = MagicMock()
                mock_llm_service_class.return_value = mock_llm_service
                mock_slack_service_class.return_value = mock_slack_service
                
                app, slack_service, llm_service = create_app()
                
                # Verify app was created
                mock_app_class.assert_called_once()
                
                # Verify services were created
                mock_llm_service_class.assert_called_once()
                mock_slack_service_class.assert_called_once()
                
                # Verify handlers were registered
                mock_create_task.assert_called_once()
                
                assert app == mock_app
                assert slack_service == mock_slack_service
                assert llm_service == mock_llm_service

    @pytest.mark.asyncio
    async def test_maintain_presence_success(self):
        """Test successful presence maintenance"""
        mock_client = AsyncMock()
        mock_client.users_setPresence.return_value = {"ok": True}
        
        # Run for a short time and then cancel
        task = asyncio.create_task(maintain_presence(mock_client))
        await asyncio.sleep(0.1)  # Let it run briefly
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Should have called users_setPresence at least once
        mock_client.users_setPresence.assert_called_with(presence="auto")

    @pytest.mark.asyncio
    async def test_maintain_presence_error(self):
        """Test presence maintenance with errors"""
        mock_client = AsyncMock()
        mock_client.users_setPresence.side_effect = Exception("API error")
        
        # Run for a short time and then cancel
        task = asyncio.create_task(maintain_presence(mock_client))
        await asyncio.sleep(0.1)  # Let it run briefly
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Should have attempted to call users_setPresence
        mock_client.users_setPresence.assert_called()

    @pytest.mark.asyncio
    async def test_run_success(self):
        """Test successful app run"""
        with patch('app.create_app') as mock_create_app, \
             patch('app.AsyncSocketModeHandler') as mock_handler_class, \
             patch('app.asyncio.create_task') as mock_create_task, \
             patch.dict(os.environ, {"SLACK_APP_TOKEN": "xapp-test-token"}):
            
            # Mock app and services
            mock_app = AsyncMock()
            mock_slack_service = AsyncMock()
            mock_llm_service = AsyncMock()
            mock_slack_service.bot_id = None
            
            mock_create_app.return_value = (mock_app, mock_slack_service, mock_llm_service)
            
            # Mock auth test response
            mock_app.client.auth_test = AsyncMock(return_value={
                "user_id": "B12345678",
                "user": "test-bot"
            })
            mock_app.client.users_setPresence = AsyncMock(return_value={"ok": True})
            
            # Mock socket mode handler
            mock_handler = AsyncMock()
            mock_handler_class.return_value = mock_handler
            
            # Mock the handler to raise an exception to break the loop
            mock_handler.start_async = AsyncMock(side_effect=KeyboardInterrupt())
            
            try:
                await run()
            except KeyboardInterrupt:
                pass
            
            # Verify app creation
            mock_create_app.assert_called_once()
            
            # Verify auth test
            mock_app.client.auth_test.assert_called_once()
            
            # Verify presence setting
            mock_app.client.users_setPresence.assert_called_with(presence="auto")
            
            # Verify bot ID was updated
            assert mock_slack_service.bot_id == "B12345678"
            
            # Verify handler creation and start
            mock_handler_class.assert_called_once_with(mock_app, "xapp-test-token")
            mock_handler.start_async.assert_called_once()
            
            # Verify services were closed
            mock_llm_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_auth_error(self):
        """Test app run with auth error"""
        with patch('app.create_app') as mock_create_app, \
             patch('app.AsyncSocketModeHandler') as mock_handler_class, \
             patch.dict(os.environ, {"SLACK_APP_TOKEN": "xapp-test-token"}):
            
            # Mock app and services
            mock_app = AsyncMock()
            mock_slack_service = AsyncMock()
            mock_llm_service = AsyncMock()
            
            mock_create_app.return_value = (mock_app, mock_slack_service, mock_llm_service)
            
            # Mock auth test to raise error
            mock_app.client.auth_test = AsyncMock(side_effect=Exception("Auth failed"))
            
            # Mock socket mode handler
            mock_handler = AsyncMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.start_async = AsyncMock(side_effect=KeyboardInterrupt())
            
            try:
                await run()
            except KeyboardInterrupt:
                pass
            
            # Should still try to start handler despite auth error
            mock_handler.start_async.assert_called_once()
            mock_llm_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_socket_mode_error(self):
        """Test app run with socket mode error"""
        with patch('app.create_app') as mock_create_app, \
             patch('app.AsyncSocketModeHandler') as mock_handler_class, \
             patch.dict(os.environ, {"SLACK_APP_TOKEN": "xapp-test-token"}):
            
            # Mock app and services
            mock_app = AsyncMock()
            mock_slack_service = AsyncMock()
            mock_llm_service = AsyncMock()
            
            mock_create_app.return_value = (mock_app, mock_slack_service, mock_llm_service)
            
            # Mock auth test
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "B12345678"})
            mock_app.client.users_setPresence = AsyncMock(return_value={"ok": True})
            
            # Mock socket mode handler to raise error
            mock_handler = AsyncMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.start_async = AsyncMock(side_effect=Exception("Socket error"))
            
            await run()
            
            # Should handle the error gracefully
            mock_handler.start_async.assert_called_once()
            mock_llm_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_presence_error(self):
        """Test app run with presence setting error"""
        with patch('app.create_app') as mock_create_app, \
             patch('app.AsyncSocketModeHandler') as mock_handler_class, \
             patch.dict(os.environ, {"SLACK_APP_TOKEN": "xapp-test-token"}):
            
            # Mock app and services
            mock_app = AsyncMock()
            mock_slack_service = AsyncMock()
            mock_llm_service = AsyncMock()
            
            mock_create_app.return_value = (mock_app, mock_slack_service, mock_llm_service)
            
            # Mock auth test
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "B12345678"})
            
            # Mock presence setting to raise error
            mock_app.client.users_setPresence = AsyncMock(side_effect=Exception("Presence error"))
            
            # Mock socket mode handler
            mock_handler = AsyncMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.start_async = AsyncMock(side_effect=KeyboardInterrupt())
            
            try:
                await run()
            except KeyboardInterrupt:
                pass
            
            # Should continue despite presence error
            mock_handler.start_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_bot_id_already_set(self):
        """Test app run when bot ID is already set"""
        with patch('app.create_app') as mock_create_app, \
             patch('app.AsyncSocketModeHandler') as mock_handler_class, \
             patch.dict(os.environ, {"SLACK_APP_TOKEN": "xapp-test-token"}):
            
            # Mock app and services
            mock_app = AsyncMock()
            mock_slack_service = AsyncMock()
            mock_llm_service = AsyncMock()
            
            # Bot ID is already set
            mock_slack_service.bot_id = "B87654321"
            
            mock_create_app.return_value = (mock_app, mock_slack_service, mock_llm_service)
            
            # Mock auth test
            mock_app.client.auth_test = AsyncMock(return_value={"user_id": "B12345678"})
            mock_app.client.users_setPresence = AsyncMock(return_value={"ok": True})
            
            # Mock socket mode handler
            mock_handler = AsyncMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.start_async = AsyncMock(side_effect=KeyboardInterrupt())
            
            try:
                await run()
            except KeyboardInterrupt:
                pass
            
            # Bot ID should not be changed
            assert mock_slack_service.bot_id == "B87654321"

    def test_main(self):
        """Test main function"""
        with patch('app.asyncio.run') as mock_asyncio_run:
            main()
            
            # Should call asyncio.run with the run function
            mock_asyncio_run.assert_called_once()
            # The argument should be the run coroutine
            args = mock_asyncio_run.call_args[0]
            assert len(args) == 1

    @pytest.mark.asyncio
    async def test_run_warning_messages(self):
        """Test that permission warning messages are displayed"""
        with patch('app.create_app') as mock_create_app, \
             patch('app.AsyncSocketModeHandler') as mock_handler_class, \
             patch('app.logger') as mock_logger, \
             patch.dict(os.environ, {"SLACK_APP_TOKEN": "xapp-test-token"}):
            
            # Mock app and services
            mock_app = AsyncMock()
            mock_slack_service = AsyncMock()
            mock_llm_service = AsyncMock()
            
            mock_create_app.return_value = (mock_app, mock_slack_service, mock_llm_service)
            
            # Mock auth test
            mock_app.client.auth_test.return_value = {"user_id": "B12345678"}
            mock_app.client.users_setPresence.return_value = {"ok": True}
            
            # Mock socket mode handler
            mock_handler = AsyncMock()
            mock_handler_class.return_value = mock_handler
            mock_handler.start_async.side_effect = KeyboardInterrupt()
            
            try:
                await run()
            except KeyboardInterrupt:
                pass
            
            # Check that warning messages were logged
            warning_calls = [call for call in mock_logger.warning.call_args_list 
                           if "PERMISSION REQUIREMENTS" in str(call)]
            assert len(warning_calls) > 0