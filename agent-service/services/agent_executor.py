"""Agent execution router - supports embedded and cloud modes.

Routes agent invocations based on AGENT_EXECUTION_MODE environment variable:
- embedded: Run agents locally in-process (current behavior)
- cloud: Proxy to LangGraph Cloud (requires LangGraph Platform credentials)
"""

import logging
import os
import sys
from contextlib import suppress
from enum import Enum

import httpx

# Add shared directory to path for Langfuse service
sys.path.insert(0, str(__file__).rsplit("/", 4)[0])
from shared.services.langfuse_service import get_langfuse_service

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Agent execution modes."""

    EMBEDDED = "embedded"
    CLOUD = "cloud"


class AgentExecutor:
    """Routes agent execution based on global AGENT_EXECUTION_MODE configuration."""

    def __init__(self):
        """Initialize agent executor with mode detection."""
        mode_str = os.getenv("AGENT_EXECUTION_MODE", "embedded").lower()
        self.mode = ExecutionMode(mode_str)

        if self.mode == ExecutionMode.CLOUD:
            # Cloud mode - initialize LangGraph SDK client
            self.langgraph_url = os.getenv("LANGGRAPH_CLOUD_URL")
            self.langgraph_api_key = os.getenv("LANGGRAPH_API_KEY")

            if not self.langgraph_url or not self.langgraph_api_key:
                raise ValueError(
                    "AGENT_EXECUTION_MODE=cloud requires LANGGRAPH_CLOUD_URL "
                    "and LANGGRAPH_API_KEY environment variables"
                )

            # Lazy import - only needed in cloud mode
            try:
                from langgraph_sdk import get_client

                self.langgraph_client = get_client(
                    url=self.langgraph_url, api_key=self.langgraph_api_key
                )
                logger.info(
                    f"Agent execution mode: CLOUD (LangGraph Platform @ {self.langgraph_url})"
                )
            except ImportError:
                raise ImportError(
                    "langgraph-sdk not installed. Install with: pip install langgraph-sdk"
                )
        else:
            # Embedded mode - current behavior
            self.langgraph_client = None
            logger.info("Agent execution mode: EMBEDDED (local)")

        # Control-plane URL for fetching agent metadata
        self.control_plane_url = os.getenv(
            "CONTROL_PLANE_URL", "http://control_plane:6001"
        )

    async def invoke_agent(self, agent_name: str, query: str, context: dict) -> dict:
        """Execute agent based on global execution mode.

        Args:
            agent_name: Name of agent to invoke
            query: User query
            context: Execution context

        Returns:
            Agent execution result

        Raises:
            ValueError: If agent not found or misconfigured
        """
        if self.mode == ExecutionMode.CLOUD:
            return await self._invoke_cloud(agent_name, query, context)
        else:
            return await self._invoke_embedded(agent_name, query, context)

    async def _invoke_embedded(
        self, agent_name: str, query: str, context: dict
    ) -> dict:
        """Execute agent locally (current behavior).

        Args:
            agent_name: Agent name
            query: User query
            context: Execution context

        Returns:
            Agent result
        """
        from services.agent_registry import get_agent

        # Get agent from local registry
        agent = get_agent(agent_name)

        # Extract trace context for distributed tracing
        trace_context = context.get("trace_context")
        parent_span = None
        langfuse_service = get_langfuse_service()

        try:
            # If we have trace context, create a parent span for the agent execution
            # This ensures all @observe calls within the agent nest properly
            if trace_context and langfuse_service and langfuse_service.enabled:
                try:
                    parent_span = langfuse_service.client.start_span(
                        trace_context=trace_context,
                        name=f"agent_{agent_name}",
                        input={"query": query, "agent_name": agent_name},
                        metadata={
                            "agent_name": agent_name,
                            "execution_mode": "embedded",
                            **{
                                k: v for k, v in context.items() if k != "trace_context"
                            },
                        },
                    )
                    logger.debug(
                        f"Created parent span for agent '{agent_name}' with trace context"
                    )
                except Exception as e:
                    logger.warning(f"Failed to create parent span for agent: {e}")

            # Check if agent is a LangGraph CompiledStateGraph
            if hasattr(agent, "ainvoke") and not hasattr(agent, "run"):
                # LangGraph graph - invoke with state dict
                result = await agent.ainvoke({"query": query, **context})
            else:
                # Regular agent with invoke/run methods
                result = await agent.invoke(query, context)

            # Update parent span with output if created
            if parent_span:
                try:
                    output_data = (
                        result.get("response", str(result))
                        if isinstance(result, dict)
                        else str(result)
                    )
                    parent_span.end(output=output_data)
                except Exception as e:
                    logger.debug(f"Failed to end parent span: {e}")

            return result

        except Exception as e:
            # End parent span with error if created
            if parent_span:
                with suppress(Exception):
                    parent_span.end(output={"error": str(e)})
            raise

    async def _invoke_cloud(self, agent_name: str, query: str, context: dict) -> dict:
        """Execute agent on LangGraph Cloud.

        Args:
            agent_name: Agent name
            query: User query
            context: Execution context

        Returns:
            Agent result from LangGraph Cloud

        Raises:
            ValueError: If agent not deployed to cloud
        """
        # Get agent deployment info from control-plane
        agent_metadata = await self._get_agent_metadata(agent_name)

        if not agent_metadata.get("langgraph_assistant_id"):
            raise ValueError(
                f"Agent '{agent_name}' not deployed to LangGraph Cloud. "
                f"Assistant ID not found in control-plane. "
                f"Deploy agent via control-plane first."
            )

        assistant_id = agent_metadata["langgraph_assistant_id"]

        # Create thread on LangGraph Cloud
        thread = await self.langgraph_client.threads.create()

        # Invoke agent on LangGraph Cloud
        run = await self.langgraph_client.runs.create(
            thread_id=thread["thread_id"],
            assistant_id=assistant_id,
            input={
                "messages": [{"role": "user", "content": query}],
            },
            config=context,
        )

        # Wait for completion
        result = await self.langgraph_client.runs.join(
            thread_id=thread["thread_id"], run_id=run["run_id"]
        )

        return result

    async def _get_agent_metadata(self, agent_name: str) -> dict:
        """Fetch agent metadata from control-plane.

        Args:
            agent_name: Agent name

        Returns:
            Agent metadata dict

        Raises:
            ValueError: If agent not found
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.control_plane_url}/api/agents/{agent_name}"
            )

            if response.status_code == 404:
                raise ValueError(f"Agent '{agent_name}' not found in control-plane")

            response.raise_for_status()
            return response.json()


# Global executor instance
_executor: AgentExecutor | None = None


def get_agent_executor() -> AgentExecutor:
    """Get or create global agent executor.

    Returns:
        AgentExecutor instance
    """
    global _executor  # noqa: PLW0603

    if _executor is None:
        _executor = AgentExecutor()

    return _executor
