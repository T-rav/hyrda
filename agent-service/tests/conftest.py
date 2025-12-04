"""Shared fixtures for agent-service tests.

This file provides common fixtures and test utilities available to all test files.
Following the pattern established in bot/tests/conftest.py
"""

from unittest.mock import AsyncMock

import pytest

from tests.agent_test_utils import (
    AgentContextBuilder,
    AgentRegistryMockFactory,
    SlackServiceMockFactory,
    TestAgentFactory,
)

# ===========================
# Agent Context Fixtures
# ===========================


@pytest.fixture
def mock_agent_context():
    """Provide standard agent context for all tests.

    Returns:
        dict: Agent context with user_id, channel, slack_service
    """
    return AgentContextBuilder.default()


@pytest.fixture
def mock_agent_context_with_thread():
    """Provide agent context with thread_ts.

    Returns:
        dict: Agent context including thread_ts
    """
    return AgentContextBuilder.with_thread()


@pytest.fixture
def agent_context_builder():
    """Provide AgentContextBuilder for custom context creation.

    Returns:
        AgentContextBuilder: Builder for creating custom agent contexts

    Example:
        def test_something(agent_context_builder):
            context = (
                agent_context_builder
                .with_user_id("U999")
                .with_channel("C999")
                .with_field("company_name", "Example Corp")
                .build()
            )
    """
    return AgentContextBuilder()


# ===========================
# Service Mock Fixtures
# ===========================


@pytest.fixture
def mock_slack_service():
    """Provide mocked Slack service.

    Returns:
        Mock: Slack service mock with send_message, thinking indicators
    """
    return SlackServiceMockFactory.create_mock()


@pytest.fixture
def mock_llm_provider():
    """Provide mocked LLM provider.

    Returns:
        AsyncMock: LLM provider with get_response method
    """
    provider = AsyncMock()
    provider.get_response.return_value = "test LLM response"
    return provider


@pytest.fixture
def mock_search_service():
    """Provide mocked search service.

    Returns:
        AsyncMock: Search service with search method
    """
    service = AsyncMock()
    service.search.return_value = []
    return service


# ===========================
# Agent Registry Fixtures
# ===========================


@pytest.fixture
def empty_agent_registry():
    """Provide empty agent registry.

    Returns:
        AgentRegistry: Empty registry for testing registration
    """
    return AgentRegistryMockFactory.create_empty()


@pytest.fixture
def agent_registry_with_agents():
    """Provide registry with 2 pre-registered test agents.

    Returns:
        AgentRegistry: Registry with test0 and test1 agents
    """
    return AgentRegistryMockFactory.create_with_agents(agent_count=2)


# ===========================
# Test Agent Fixtures
# ===========================


@pytest.fixture
def simple_test_agent():
    """Provide simple test agent class.

    Returns:
        type[BaseAgent]: Test agent class with name="test"
    """
    return TestAgentFactory.create_simple_agent()


@pytest.fixture
def test_agent_with_aliases():
    """Provide test agent with aliases.

    Returns:
        type[BaseAgent]: Test agent with aliases ["t", "tst"]
    """
    return TestAgentFactory.create_agent_with_aliases()


# ===========================
# Sample Data Fixtures
# ===========================


@pytest.fixture
def sample_company_data():
    """Provide sample company data for testing company profile agent.

    Returns:
        dict: Company data structure
    """
    return {
        "company_name": "Example Corp",
        "industry": "Technology",
        "size": "500-1000 employees",
        "location": "San Francisco, CA",
        "website": "https://example.com",
    }


@pytest.fixture
def sample_meddic_data():
    """Provide sample MEDDIC data for testing MEDDIC agent.

    Returns:
        dict: MEDDIC assessment data
    """
    return {
        "metrics": "20% cost reduction",
        "economic_buyer": "CFO Jane Smith",
        "decision_criteria": "ROI, security, scalability",
        "decision_process": "3-month evaluation",
        "identify_pain": "Manual processes causing delays",
        "champion": "VP Engineering John Doe",
    }


# ===========================
# Event Loop Fixtures
# ===========================


@pytest.fixture(scope="session")
def event_loop():
    """Provide event loop for async tests.

    Returns:
        asyncio.AbstractEventLoop: Event loop for the test session
    """
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
