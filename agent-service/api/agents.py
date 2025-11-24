"""Agent execution API endpoints."""

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents import agent_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentInvokeRequest(BaseModel):
    """Request model for agent invocation."""

    query: str = Field(..., description="User query for the agent")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context for agent execution"
    )


class AgentInvokeResponse(BaseModel):
    """Response model for agent invocation."""

    agent_name: str
    response: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentListResponse(BaseModel):
    """Response model for listing agents."""

    agents: list[dict[str, Any]]


@router.get("", response_model=AgentListResponse)
async def list_agents():
    """List all available agents.

    Returns:
        List of agent names and their metadata
    """
    agents = agent_registry.list_agents()
    return AgentListResponse(
        agents=[
            {
                "name": agent["name"],
                "aliases": agent.get("aliases", []),
                "description": getattr(agent["agent_class"], "description", ""),
            }
            for agent in agents
        ]
    )


@router.get("/{agent_name}")
async def get_agent_info(agent_name: str):
    """Get information about a specific agent.

    Args:
        agent_name: Name or alias of the agent

    Returns:
        Agent metadata including schema information

    Raises:
        HTTPException: If agent not found
    """
    agent_info = agent_registry.get(agent_name)
    if not agent_info:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent_class = agent_info["agent_class"]
    primary_name = agent_registry.get_primary_name(agent_name)

    return {
        "name": primary_name,
        "aliases": agent_info.get("aliases", []),
        "description": getattr(agent_class, "description", ""),
        "is_alias": agent_name.lower() != primary_name,
    }


@router.post("/{agent_name}/invoke", response_model=AgentInvokeResponse)
async def invoke_agent(agent_name: str, request: AgentInvokeRequest):
    """Invoke an agent with a query.

    Args:
        agent_name: Name or alias of the agent to invoke
        request: Agent invocation request with query and context

    Returns:
        Agent execution result

    Raises:
        HTTPException: If agent not found or execution fails
    """
    from services.metrics_service import get_metrics_service

    logger.info(f"Invoking agent '{agent_name}' with query: {request.query[:100]}...")

    # Get agent from registry
    agent_info = agent_registry.get(agent_name)
    if not agent_info:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    # Track invocation timing
    start_time = time.time()
    status = "error"
    primary_name = agent_registry.get_primary_name(agent_name)

    try:
        # Instantiate and run agent
        agent_class = agent_info["agent_class"]
        agent_instance = agent_class()

        # Execute agent
        result = await agent_instance.run(request.query, request.context)

        status = "success"
        return AgentInvokeResponse(
            agent_name=primary_name,
            response=result.get("response", ""),
            metadata=result.get("metadata", {}),
        )

    except Exception as e:
        logger.error(f"Error invoking agent '{agent_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Agent execution failed: {str(e)}"
        ) from e
    finally:
        # Record metrics (tracks ALL invocations - Slack, API, LibreChat, etc.)
        duration = time.time() - start_time
        metrics_service = get_metrics_service()
        if metrics_service:
            metrics_service.record_agent_invocation(
                agent_name=primary_name, status=status, duration=duration
            )


@router.post("/{agent_name}/stream")
async def stream_agent(agent_name: str, request: AgentInvokeRequest):
    """Invoke an agent with streaming response.

    Args:
        agent_name: Name or alias of the agent to invoke
        request: Agent invocation request with query and context

    Returns:
        Streaming response with agent output

    Raises:
        HTTPException: If agent not found or execution fails
    """
    logger.info(
        f"Streaming agent '{agent_name}' with query: {request.query[:100]}..."
    )

    # Get agent from registry
    agent_info = agent_registry.get(agent_name)
    if not agent_info:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    async def event_generator():
        """Generate server-sent events from agent execution."""
        try:
            agent_class = agent_info["agent_class"]
            agent_instance = agent_class()

            # Check if agent supports streaming
            if not hasattr(agent_instance, "stream"):
                # Fallback to non-streaming execution
                result = await agent_instance.run(request.query, request.context)
                yield f"data: {result.get('response', '')}\n\n"
                return

            # Stream agent output
            async for chunk in agent_instance.stream(request.query, request.context):
                yield f"data: {chunk}\n\n"

        except Exception as e:
            logger.error(f"Error streaming agent '{agent_name}': {e}", exc_info=True)
            yield f"data: ERROR: {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
