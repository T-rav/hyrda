"""State definitions for help agent workflow.

Defines data structures for the help agent that lists available agents
filtered by user permissions.
"""

from typing import Annotated, Any

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict


class AgentInfo(BaseModel):
    """Information about an available agent."""

    name: str
    display_name: str
    description: str
    aliases: list[str]
    is_enabled: bool
    is_system: bool


class _HelpAgentStateRequired(TypedDict):
    """Required fields for HelpAgentState."""

    query: str  # Original user query (ignored, but part of interface)
    user_id: str  # Slack user ID for permission checking


class HelpAgentState(_HelpAgentStateRequired, total=False):
    """Main state for help agent workflow.

    Tracks user context and available agents filtered by permissions.

    Attributes:
        query: Original user query (REQUIRED)
        user_id: Slack user ID for permission checking (REQUIRED)
        messages: Conversation history
        user_groups: Groups the user belongs to
        all_agents: All registered agents from control plane
        accessible_agents: Agents filtered by user permissions
        response: Final response to send to user
    """

    messages: Annotated[list[MessageLikeRepresentation], add_messages]
    user_groups: list[str]
    all_agents: list[AgentInfo]
    accessible_agents: list[AgentInfo]
    response: str
    metadata: dict[str, Any]


class HelpAgentInputState(TypedDict):
    """Input to the help agent graph."""

    query: str
    user_id: str


class HelpAgentOutputState(TypedDict):
    """Output from the help agent graph."""

    response: str
    metadata: dict[str, Any]
