"""Tests for ProfileAgent SQLite checkpointer initialization."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestProfileAgentCheckpointer:
    """Test SQLite checkpointer initialization in ProfileAgent."""

    @pytest.mark.asyncio
    async def test_checkpointer_initialization(self):
        """Test that AsyncSqliteSaver checkpointer initializes correctly."""
        # Create temporary directory for test checkpoint
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = Path(tmpdir) / "test_profile_checkpoints.db"

            # Set environment variable for test
            with patch.dict(os.environ, {"AGENT_CHECKPOINT_DIR": str(tmpdir)}):
                # Reset singleton state
                import agents.profile_agent as profile_module

                profile_module._checkpointer = None
                profile_module._checkpointer_initialized = False
                profile_module.profile_researcher = None

                # Import after resetting singletons
                from agents.profile_agent import ProfileAgent

                # Mock LangGraph components to avoid full initialization
                with (
                    patch(
                        "agents.profile_agent.build_profile_researcher"
                    ) as mock_build,
                    patch("agents.profile_agent.detect_profile_type") as mock_detect,
                    patch("agents.profile_agent.extract_focus_area") as mock_extract,
                ):
                    # Mock graph build
                    mock_graph = AsyncMock()
                    mock_graph.ainvoke = AsyncMock(
                        return_value={"final_report": "Test report"}
                    )
                    mock_graph.aget_state = AsyncMock(
                        return_value=Mock(values={"final_report": "Test report"})
                    )
                    mock_build.return_value = mock_graph

                    # Mock profile type detection
                    mock_detect.return_value = "company"
                    mock_extract.return_value = None

                    # Create agent (lazy init, graph not built yet)
                    agent = ProfileAgent()
                    assert agent.graph is None

                    # Create minimal context
                    context = {
                        "llm_service": Mock(),
                        "slack_service": Mock(),
                        "channel": "C123",
                        "user_id": "U123",
                        "thread_ts": "1234.5678",
                    }

                    # Trigger lazy initialization by calling run()
                    await agent.run("Test query", context)

                    # Verify checkpointer was initialized
                    assert profile_module._checkpointer_initialized
                    assert profile_module._checkpointer is not None

                    # Verify checkpoint database file was created
                    assert checkpoint_path.exists()
                    assert checkpoint_path.stat().st_size > 0

                    # Verify graph was built with checkpointer
                    mock_build.assert_called_once()
                    call_kwargs = mock_build.call_args[1]
                    assert "checkpointer" in call_kwargs
                    assert call_kwargs["checkpointer"] is not None

    @pytest.mark.asyncio
    async def test_checkpointer_singleton_pattern(self):
        """Test that checkpointer follows singleton pattern."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.dict(os.environ, {"AGENT_CHECKPOINT_DIR": str(tmpdir)}),
        ):
            # Reset singleton state
            import agents.profile_agent as profile_module

            profile_module._checkpointer = None
            profile_module._checkpointer_initialized = False
            profile_module.profile_researcher = None

            from agents.profile_agent import ProfileAgent

            with (
                patch("agents.profile_agent.build_profile_researcher") as mock_build,
                patch("agents.profile_agent.detect_profile_type"),
                patch("agents.profile_agent.extract_focus_area"),
            ):
                mock_graph = AsyncMock()
                mock_graph.ainvoke = AsyncMock(return_value={"final_report": "Test"})
                mock_graph.aget_state = AsyncMock(
                    return_value=Mock(values={"final_report": "Test"})
                )
                mock_build.return_value = mock_graph

                context = {
                    "llm_service": Mock(),
                    "slack_service": Mock(),
                    "channel": "C123",
                    "user_id": "U123",
                    "thread_ts": "1234.5678",
                }

                # Create two agent instances
                agent1 = ProfileAgent()
                agent2 = ProfileAgent()

                # Trigger initialization on first agent
                await agent1.run("Test query 1", context)
                checkpointer1 = profile_module._checkpointer

                # Trigger initialization on second agent
                await agent2.run("Test query 2", context)
                checkpointer2 = profile_module._checkpointer

                # Verify same checkpointer instance is used
                assert checkpointer1 is checkpointer2
                assert profile_module._checkpointer_initialized  # Should still be True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
