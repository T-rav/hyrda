"""Tests for MeddicAgent."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.meddic_agent import MeddicAgent
from tests.agent_test_utils import AgentContextBuilder


class TestMeddicAgent:
    """Tests for MeddicAgent"""

    @pytest.mark.asyncio
    async def test_meddic_agent_run(self):
        """Test MeddicAgent execution"""
        agent = MeddicAgent()
        context = AgentContextBuilder.default()

        result = await agent.run("analyze this deal", context)

        assert "response" in result
        assert "metadata" in result
        assert "MEDDIC" in result["response"]
        assert "analyze this deal" in result["response"]

    @pytest.mark.asyncio
    async def test_meddic_agent_has_alias(self):
        """Test that MeddicAgent has medic alias"""
        assert "medic" in MeddicAgent.aliases

    @pytest.mark.asyncio
    async def test_meddic_agent_invalid_context(self):
        """Test MeddicAgent with invalid context"""
        agent = MeddicAgent()
        context = AgentContextBuilder.invalid_missing_channel()

        result = await agent.run("test query", context)

        assert "response" in result
        assert "error" in result["metadata"]
