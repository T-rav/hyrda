"""Tests for MeddicAgent SQLite checkpointer initialization."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestMeddicAgentCheckpointer:
    """Test SQLite checkpointer initialization in MeddicAgent."""

    @pytest.mark.asyncio
    async def test_checkpointer_initialization(self):
        """Test that AsyncSqliteSaver checkpointer initializes correctly."""
        # Create temporary directory for test checkpoint
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = Path(tmpdir) / "test_meddic_checkpoints.db"

            # Set environment variable for test
            with patch.dict(os.environ, {"AGENT_CHECKPOINT_DIR": str(tmpdir)}):
                # Reset singleton state
                import agents.meddic_agent as meddic_module

                meddic_module._checkpointer = None
                meddic_module._checkpointer_initialized = False

                # Import after resetting singletons
                from agents.meddic_agent import MeddicAgent

                # Mock LangGraph components to avoid full initialization
                with (
                    patch("agents.meddic_agent.build_meddpicc_coach") as mock_build,
                ):
                    # Mock graph build
                    mock_graph = AsyncMock()
                    mock_graph.ainvoke = AsyncMock(
                        return_value={
                            "structured_meddpicc": {
                                "metrics": "Test metrics",
                            }
                        }
                    )
                    mock_graph.checkpointer = Mock()
                    mock_build.return_value = mock_graph

                    # Create agent (lazy init, graph not built yet)
                    agent = MeddicAgent()
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
                    await agent.run("Test sales notes", context)

                    # Verify checkpointer was initialized
                    assert meddic_module._checkpointer_initialized
                    assert meddic_module._checkpointer is not None

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
            import agents.meddic_agent as meddic_module

            meddic_module._checkpointer = None
            meddic_module._checkpointer_initialized = False

            from agents.meddic_agent import MeddicAgent

            with patch("agents.meddic_agent.build_meddpicc_coach") as mock_build:
                mock_graph = AsyncMock()
                mock_graph.ainvoke = AsyncMock(
                    return_value={"structured_meddpicc": {"metrics": "Test"}}
                )
                mock_graph.checkpointer = Mock()
                mock_build.return_value = mock_graph

                context = {
                    "llm_service": Mock(),
                    "slack_service": Mock(),
                    "channel": "C123",
                    "user_id": "U123",
                    "thread_ts": "1234.5678",
                }

                # Create two agent instances
                agent1 = MeddicAgent()
                agent2 = MeddicAgent()

                # Trigger initialization on first agent
                await agent1.run("Test notes 1", context)
                checkpointer1 = meddic_module._checkpointer

                # Trigger initialization on second agent
                await agent2.run("Test notes 2", context)
                checkpointer2 = meddic_module._checkpointer

                # Verify same checkpointer instance is used
                assert checkpointer1 is checkpointer2
                assert meddic_module._checkpointer_initialized  # Should still be True

    @pytest.mark.asyncio
    async def test_checkpointer_persists_across_calls(self):
        """Test that checkpointer persists state across multiple calls."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.dict(os.environ, {"AGENT_CHECKPOINT_DIR": str(tmpdir)}),
        ):
            checkpoint_path = Path(tmpdir) / "test_meddic_checkpoints.db"

            # Reset singleton state
            import agents.meddic_agent as meddic_module

            meddic_module._checkpointer = None
            meddic_module._checkpointer_initialized = False

            from agents.meddic_agent import MeddicAgent

            with patch("agents.meddic_agent.build_meddpicc_coach") as mock_build:
                mock_graph = AsyncMock()
                mock_graph.ainvoke = AsyncMock(
                    return_value={"structured_meddpicc": {"metrics": "Test"}}
                )
                mock_graph.checkpointer = Mock()
                mock_build.return_value = mock_graph

                context = {
                    "llm_service": Mock(),
                    "slack_service": Mock(),
                    "channel": "C123",
                    "user_id": "U123",
                    "thread_ts": "1234.5678",
                }

                agent = MeddicAgent()

                # First call - initializes checkpointer
                await agent.run("First call", context)
                assert checkpoint_path.exists()
                first_size = checkpoint_path.stat().st_size

                # Second call - reuses same checkpointer
                await agent.run("Second call", context)
                # Database should exist and potentially have grown
                assert checkpoint_path.exists()
                second_size = checkpoint_path.stat().st_size
                assert second_size >= first_size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
