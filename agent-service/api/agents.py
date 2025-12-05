"""Agent execution API endpoints."""

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from dependencies.auth import require_service_auth
from services.agent_executor import get_agent_executor
from services.agent_registry import (
    get as get_agent,
)
from services.agent_registry import (
    get_primary_name,
)
from services.agent_registry import (
    list_agents as list_agents_func,
)
from services.metrics_service import get_metrics_service
from utils.validation import validate_agent_name

logger = logging.getLogger(__name__)

# Router with service-to-service authentication required for all endpoints
router = APIRouter(
    prefix="/agents",
    tags=["agents"],
    dependencies=[Depends(require_service_auth)]
)


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
    agents = list_agents_func()
    return AgentListResponse(
        agents=[
            {
                "name": agent["name"],
                "aliases": agent.get("aliases", []),
                "description": agent.get("description", "")
                or (
                    getattr(agent.get("agent_class"), "description", "")
                    if agent.get("agent_class")
                    else ""
                ),
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
        HTTPException: If agent not found or invalid
    """
    # Validate agent name to prevent injection
    is_valid, error_msg = validate_agent_name(agent_name)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid agent name: {error_msg}")

    agent_info = get_agent(agent_name)
    if not agent_info:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent_class = agent_info.get("agent_class")
    primary_name = get_primary_name(agent_name) or agent_name.lower()

    return {
        "name": primary_name,
        "aliases": agent_info.get("aliases", []),
        "description": agent_info.get("description", "")
        or (getattr(agent_class, "description", "") if agent_class else ""),
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
        HTTPException: If agent not found, invalid, or execution fails
    """
    # Validate agent name to prevent injection
    is_valid, error_msg = validate_agent_name(agent_name)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid agent name: {error_msg}")

    logger.info(f"Invoking agent '{agent_name}' with query: {request.query[:100]}...")

    # Get primary agent name
    primary_name = get_primary_name(agent_name) or agent_name.lower()

    # Track invocation timing
    start_time = time.time()
    status = "error"

    try:
        # Execute agent via AgentExecutor (handles embedded/cloud routing)
        agent_executor = get_agent_executor()
        result = await agent_executor.invoke_agent(
            agent_name=primary_name, query=request.query, context=request.context
        )

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
    logger.info(f"Streaming agent '{agent_name}' with query: {request.query[:100]}...")

    # Get agent from registry
    agent_info = get_agent(agent_name)
    if not agent_info:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    # Check if agent class is available
    agent_class = agent_info.get("agent_class")
    if not agent_class:

        async def error_generator():
            """Error Generator."""
            yield f"data: ERROR: Agent '{agent_name}' is not available (class not loaded)\n\n"

        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream",
        )

    async def event_generator():
        """Generate server-sent events from agent execution."""
        try:
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
