"""
Tests for Agent Processes handler.

Tests agent process definitions and execution using factory patterns.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from bot.handlers.agent_processes import (
    AGENT_PROCESSES,
    get_agent_blocks,
    get_available_processes,
    run_agent_process,
)
from bot.models.service_responses import ApiResponse


# TDD Factory Patterns for Agent Process Testing
class MockProcessFactory:
    """Factory for creating mock subprocess instances"""

    @staticmethod
    def create_successful_process(pid: int = 12345) -> Mock:
        """Create mock process that starts successfully"""
        mock_process = Mock()
        mock_process.pid = pid
        return mock_process

    @staticmethod
    def create_failed_process() -> Exception:
        """Create exception for process startup failure"""
        return Exception("Test error")


class AgentProcessDataFactory:
    """Factory for creating test data for agent processes"""

    @staticmethod
    def get_first_process_id() -> str:
        """Get first available process ID for testing"""
        return list(AGENT_PROCESSES.keys())[0]

    @staticmethod
    def create_unknown_process_id() -> str:
        """Create unknown process ID for error testing"""
        return "nonexistent_process"

    @staticmethod
    def create_valid_process_names() -> list[str]:
        """Create list of all valid process names"""
        return list(AGENT_PROCESSES.keys())


class ApiResponseFactory:
    """Factory for creating ApiResponse instances for testing"""

    @staticmethod
    def create_successful_response(
        name: str = "Test Process",
        status: str = "started",
        pid: int = 12345,
    ) -> ApiResponse:
        """Create successful API response"""
        return ApiResponse(
            success=True,
            data={
                "name": name,
                "status": status,
                "pid": pid,
            },
            timestamp=datetime.now(),
        )

    @staticmethod
    def create_failed_response(error_message: str = "Test error") -> ApiResponse:
        """Create failed API response"""
        return ApiResponse(
            success=False,
            error_message=error_message,
            timestamp=datetime.now(),
        )

    @staticmethod
    def create_process_start_response(
        process_id: str,
        process_name: str = "Test Process",
        pid: int = 12345,
    ) -> ApiResponse:
        """Create response for successful process start"""
        return ApiResponse(
            success=True,
            data={
                "process_id": process_id,
                "name": process_name,
                "status": "started",
                "pid": pid,
            },
            timestamp=datetime.now(),
        )

    @staticmethod
    def create_process_error_response(
        process_id: str,
        error_message: str = "Test error",
    ) -> ApiResponse:
        """Create response for process error"""
        return ApiResponse(
            success=False,
            error_message=error_message,
            data={"process_id": process_id},
            timestamp=datetime.now(),
        )


class UserDataFactory:
    """Factory for creating test user data"""

    @staticmethod
    def create_test_user_id() -> str:
        """Create test user ID"""
        return "U123456"

    @staticmethod
    def create_different_user_id() -> str:
        """Create different test user ID"""
        return "U789012"


class TestAgentProcesses:
    """Test cases for agent process definitions using factory patterns"""

    def test_agent_processes_structure(self):
        """Test that AGENT_PROCESSES has expected structure"""
        assert isinstance(AGENT_PROCESSES, dict)
        assert len(AGENT_PROCESSES) > 0

        for name, config in AGENT_PROCESSES.items():
            assert isinstance(name, str)
            assert isinstance(config, dict)
            assert "name" in config
            assert "description" in config
            assert "command" in config

    def test_get_available_processes(self):
        """Test getting available processes"""
        processes = get_available_processes()
        assert processes == AGENT_PROCESSES
        assert isinstance(processes, dict)

    @pytest.mark.asyncio
    async def test_run_agent_process_success(self):
        """Test successful agent process execution"""
        process_id = AgentProcessDataFactory.get_first_process_id()
        mock_process = MockProcessFactory.create_successful_process()

        with patch("asyncio.create_subprocess_shell") as mock_create:
            mock_create.return_value = mock_process

            result = await run_agent_process(process_id)

            assert result.success is True
            assert result.data["process_id"] == process_id
            assert result.data["status"] == "started"
            assert result.data["pid"] == mock_process.pid
            assert "name" in result.data

    @pytest.mark.asyncio
    async def test_run_agent_process_with_different_pid(self):
        """Test successful agent process execution with different PID"""
        process_id = AgentProcessDataFactory.get_first_process_id()
        custom_pid = 99999
        mock_process = MockProcessFactory.create_successful_process(pid=custom_pid)

        with patch("asyncio.create_subprocess_shell") as mock_create:
            mock_create.return_value = mock_process

            result = await run_agent_process(process_id)

            assert result.success is True
            assert result.data["pid"] == custom_pid

    @pytest.mark.asyncio
    async def test_run_agent_process_unknown(self):
        """Test running unknown agent process"""
        unknown_process_id = AgentProcessDataFactory.create_unknown_process_id()
        result = await run_agent_process(unknown_process_id)

        assert result.success is False
        assert "Unknown agent process" in result.error_message

    @pytest.mark.asyncio
    async def test_run_agent_process_exception(self):
        """Test agent process execution with exception"""
        process_id = AgentProcessDataFactory.get_first_process_id()
        test_exception = MockProcessFactory.create_failed_process()

        with patch("asyncio.create_subprocess_shell", side_effect=test_exception):
            result = await run_agent_process(process_id)

            assert result.success is False
            assert "Test error" in result.error_message
            assert result.data["process_id"] == process_id

    def test_get_agent_blocks_success(self):
        """Test getting agent blocks for successful result"""
        result = ApiResponseFactory.create_successful_response()
        user_id = UserDataFactory.create_test_user_id()

        blocks = get_agent_blocks(result, user_id)

        assert isinstance(blocks, list)
        assert len(blocks) == 3
        assert blocks[0]["type"] == "section"
        assert "🚀" in blocks[0]["text"]["text"]
        assert "Test Process" in blocks[0]["text"]["text"]

    def test_get_agent_blocks_success_custom_process(self):
        """Test getting agent blocks for successful result with custom process name"""
        custom_name = "Data Processing Job"
        result = ApiResponseFactory.create_successful_response(name=custom_name)
        user_id = UserDataFactory.create_test_user_id()

        blocks = get_agent_blocks(result, user_id)

        assert isinstance(blocks, list)
        assert len(blocks) == 3
        assert custom_name in blocks[0]["text"]["text"]

    def test_get_agent_blocks_failure(self):
        """Test getting agent blocks for failed result"""
        result = ApiResponseFactory.create_failed_response()
        user_id = UserDataFactory.create_test_user_id()

        blocks = get_agent_blocks(result, user_id)

        assert isinstance(blocks, list)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "section"
        assert "❌" in blocks[0]["text"]["text"]
        assert "Test error" in blocks[0]["text"]["text"]

    def test_get_agent_blocks_failure_custom_error(self):
        """Test getting agent blocks for failed result with custom error"""
        custom_error = "Custom error message"
        result = ApiResponseFactory.create_failed_response(error_message=custom_error)
        user_id = UserDataFactory.create_different_user_id()

        blocks = get_agent_blocks(result, user_id)

        assert isinstance(blocks, list)
        assert len(blocks) == 1
        assert custom_error in blocks[0]["text"]["text"]

    def test_process_descriptions_are_meaningful(self):
        """Test that process descriptions are meaningful"""
        for _name, config in AGENT_PROCESSES.items():
            description = config["description"]
            assert isinstance(description, str)
            assert len(description.strip()) > 5
            assert not description.isspace()

    def test_no_duplicate_process_names(self):
        """Test that there are no duplicate process names"""
        names = AgentProcessDataFactory.create_valid_process_names()
        assert len(names) == len(set(names))

    def test_all_processes_have_valid_commands(self):
        """Test that all agent processes have valid commands"""
        for _name, config in AGENT_PROCESSES.items():
            command = config["command"]
            assert isinstance(command, str)
            assert len(command.strip()) > 0
