"""
Tests for Agent Processes handler.

Tests agent process definitions and execution.
"""

from unittest.mock import Mock, patch

import pytest

from bot.handlers.agent_processes import (
    AGENT_PROCESSES,
    get_agent_blocks,
    get_available_processes,
    run_agent_process,
)


class TestAgentProcesses:
    """Test cases for agent process definitions"""

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
        process_id = list(AGENT_PROCESSES.keys())[0]  # Get first available process

        with patch("asyncio.create_subprocess_shell") as mock_create:
            mock_process = Mock()
            mock_process.pid = 12345
            mock_create.return_value = mock_process

            result = await run_agent_process(process_id)

            assert result.success is True
            assert result.data["process_id"] == process_id
            assert result.data["status"] == "started"
            assert result.data["pid"] == 12345
            assert "name" in result.data

    @pytest.mark.asyncio
    async def test_run_agent_process_unknown(self):
        """Test running unknown agent process"""
        result = await run_agent_process("nonexistent_process")

        assert result.success is False
        assert "Unknown agent process" in result.error_message

    @pytest.mark.asyncio
    async def test_run_agent_process_exception(self):
        """Test agent process execution with exception"""
        process_id = list(AGENT_PROCESSES.keys())[0]

        with patch(
            "asyncio.create_subprocess_shell", side_effect=Exception("Test error")
        ):
            result = await run_agent_process(process_id)

            assert result.success is False
            assert "Test error" in result.error_message
            assert result.data["process_id"] == process_id

    def test_get_agent_blocks_success(self):
        """Test getting agent blocks for successful result"""
        from datetime import datetime

        from bot.models.service_responses import ApiResponse

        result = ApiResponse(
            success=True,
            data={
                "name": "Test Process",
                "status": "started",
                "pid": 12345,
            },
            timestamp=datetime.now(),
        )
        user_id = "U123456"

        blocks = get_agent_blocks(result, user_id)

        assert isinstance(blocks, list)
        assert len(blocks) == 3
        assert blocks[0]["type"] == "section"
        assert "🚀" in blocks[0]["text"]["text"]
        assert "Test Process" in blocks[0]["text"]["text"]

    def test_get_agent_blocks_failure(self):
        """Test getting agent blocks for failed result"""
        from datetime import datetime

        from bot.models.service_responses import ApiResponse

        result = ApiResponse(
            success=False, error_message="Test error", timestamp=datetime.now()
        )
        user_id = "U123456"

        blocks = get_agent_blocks(result, user_id)

        assert isinstance(blocks, list)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "section"
        assert "❌" in blocks[0]["text"]["text"]
        assert "Test error" in blocks[0]["text"]["text"]

    def test_process_descriptions_are_meaningful(self):
        """Test that process descriptions are meaningful"""
        for _name, config in AGENT_PROCESSES.items():
            description = config["description"]
            assert isinstance(description, str)
            assert len(description.strip()) > 5
            assert not description.isspace()

    def test_no_duplicate_process_names(self):
        """Test that there are no duplicate process names"""
        names = list(AGENT_PROCESSES.keys())
        assert len(names) == len(set(names))

    def test_all_processes_have_valid_commands(self):
        """Test that all agent processes have valid commands"""
        for _name, config in AGENT_PROCESSES.items():
            command = config["command"]
            assert isinstance(command, str)
            assert len(command.strip()) > 0
