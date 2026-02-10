"""Agent execution API endpoints."""

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from clients.agent_client import agent_client
from dependencies.auth import require_service_auth
from services.metrics_service import get_metrics_service
from utils.validation import validate_agent_name

logger = logging.getLogger(__name__)

# Router for agent endpoints
# Note: Auth is handled per-endpoint (service-to-service OR user-level RBAC)
router = APIRouter(
    prefix="/agents",
    tags=["agents"],
)


class AgentInvokeRequest(BaseModel):
    """Request model for agent invocation.

    Security: user_id is NEVER accepted from client.
    User identity comes from verified JWT token only.
    """

    query: str = Field(..., description="User query for the agent")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context for agent execution"
    )
    # NO user_id field! Identity comes from JWT.


class AgentInvokeResponse(BaseModel):
    """Response model for agent invocation."""

    agent_name: str
    response: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentListResponse(BaseModel):
    """Response model for listing agents."""

    agents: list[dict[str, Any]]


@router.get(
    "", response_model=AgentListResponse, dependencies=[Depends(require_service_auth)]
)
async def list_agents():
    """List all available agents from local registry.

    Returns agents from langgraph.json (source of truth).
    Control plane is checked for authorization during agent invocation.

    Returns:
        List of agent names and their metadata
    """
    from services import agent_registry

    try:
        agents = agent_registry.list_agents()
        return AgentListResponse(
            agents=[
                {
                    "name": a["name"],
                    "aliases": a.get("aliases", []),
                    "description": a.get("description", "No description"),
                }
                for a in agents
            ]
        )
    except Exception as e:
        logger.error(f"Failed to list agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")


@router.get("/{agent_name}", dependencies=[Depends(require_service_auth)])
async def get_agent_info(agent_name: str):
    """Get information about a specific agent from control plane.

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

    try:
        # Discover agent from control plane
        agent_info = await agent_client.discover_agent(agent_name)

        return {
            "name": agent_info["agent_name"],
            "display_name": agent_info.get("display_name", agent_info["agent_name"]),
            "endpoint_url": agent_info.get("endpoint_url"),
            "is_cloud": agent_info.get("is_cloud", False),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting agent info: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get agent info: {str(e)}"
        )


@router.post("/{agent_name}/invoke", response_model=AgentInvokeResponse)
async def invoke_agent(
    agent_name: str, request: AgentInvokeRequest, http_request: Request
):
    """Invoke an agent with a query.

    Security (3 auth methods):
    1. User requests: MUST include JWT token (Authorization: Bearer <token>)
    2. External API requests: MUST include service account API key (X-API-Key or Authorization: Bearer sa_...)
    3. Internal service requests: MUST include X-Service-Token header

    user_id is NEVER accepted from request body (security!)

    Args:
        agent_name: Name or alias of the agent to invoke
        request: Agent invocation request with query and context
        http_request: FastAPI request object (for auth headers)

    Returns:
        Agent execution result

    Raises:
        HTTPException: If agent not found, invalid, or execution fails
    """
    # Validate agent name to prevent injection
    is_valid, error_msg = validate_agent_name(agent_name)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid agent name: {error_msg}")

    # Discover agent from control plane (this validates it exists and is enabled)
    try:
        agent_info = await agent_client.discover_agent(agent_name)
        primary_name = agent_info["agent_name"]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Centralized authorization (handles JWT, service accounts, internal tokens)
    from dependencies.agent_auth import authorize_agent_request

    auth_result = await authorize_agent_request(agent_name, agent_info, http_request)

    logger.info(
        f"Invoking agent '{agent_name}' (auth: {auth_result.auth_type}, "
        f"user: {auth_result.user_id or 'none'})"
    )

    # Extract or create trace context for unified observability
    from shared.services.langfuse_service import get_langfuse_service
    from shared.utils.trace_propagation import extract_trace_context

    trace_context = extract_trace_context(dict(http_request.headers))
    langfuse_service = get_langfuse_service()

    # If no parent trace context, create root span (standalone entry point)
    if not trace_context and langfuse_service:
        trace_id, root_obs_id = langfuse_service.start_root_span(
            name="agent_service_invoke",
            input_data={"agent_name": primary_name, "query": request.query},
            metadata={
                "entry_point": "http",
                "auth_type": auth_result.auth_type,
                "user_id": auth_result.user_id,
                "service_account": auth_result.service_account_name,
            },
        )
        trace_context = {"trace_id": trace_id, "parent_span_id": root_obs_id}
        logger.debug(f"Created root trace: {trace_id}")

    # Track invocation timing
    start_time = time.time()
    status = "error"

    try:
        # Execute agent via AgentClient (HTTP-only, works for embedded and cloud)
        # AgentClient queries control plane for endpoint, then invokes via HTTP
        context = request.context.copy()

        # Add user_id to context (from JWT/service token, NEVER from request body!)
        if auth_result.user_id:
            context["user_id"] = auth_result.user_id

        # Add auth metadata for audit trail
        context["auth_type"] = auth_result.auth_type

        # Add trace context to context for downstream propagation
        if trace_context:
            context["trace_context"] = trace_context

        result = await agent_client.invoke(
            agent_name=primary_name, query=request.query, context=context
        )

        status = "success"
        return AgentInvokeResponse(
            agent_name=primary_name,
            response=result.get("response", ""),
            metadata=result.get("metadata", {}),
        )

    except ValueError as e:
        # Agent not found or not registered
        raise HTTPException(status_code=404, detail=str(e))
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
async def stream_agent(
    agent_name: str, request: AgentInvokeRequest, http_request: Request
):
    """Invoke an agent with streaming response via HTTP.

    Security (3 auth methods):
    1. User requests: MUST include JWT token (Authorization: Bearer <token>)
    2. External API requests: MUST include service account API key (X-API-Key or Authorization: Bearer sa_...)
    3. Internal service requests: MUST include X-Service-Token header

    user_id is NEVER accepted from request body (security!)

    Args:
        agent_name: Name or alias of the agent to invoke
        request: Agent invocation request with query and context
        http_request: FastAPI request object (for auth headers)

    Returns:
        Streaming response with agent output

    Raises:
        HTTPException: If agent not found or execution fails
    """
    # Validate agent name to prevent injection
    is_valid, error_msg = validate_agent_name(agent_name)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid agent name: {error_msg}")

    # Discover agent from control plane
    try:
        agent_info = await agent_client.discover_agent(agent_name)
        primary_name = agent_info["agent_name"]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Centralized authorization (handles JWT, service accounts, internal tokens)
    from dependencies.agent_auth import authorize_agent_request

    auth_result = await authorize_agent_request(agent_name, agent_info, http_request)

    logger.info(
        f"Streaming agent '{agent_name}' (auth: {auth_result.auth_type}, "
        f"user: {auth_result.user_id or 'none'})"
    )

    async def event_generator():
        """Generate server-sent events from agent execution via HTTP."""
        try:
            # Stream agent output via AgentClient (HTTP-only)
            context = request.context.copy()

            # Add user_id to context (from JWT/service token, NEVER from request body!)
            if auth_result.user_id:
                context["user_id"] = auth_result.user_id

            # Add auth metadata for audit trail
            context["auth_type"] = auth_result.auth_type

            # Extract and propagate trace context for distributed tracing
            from shared.utils.trace_propagation import extract_trace_context

            trace_context = extract_trace_context(dict(http_request.headers))
            if trace_context:
                context["trace_context"] = trace_context
                logger.info(f"Propagating trace context to agent: {trace_context}")

            async for chunk in agent_client.stream(
                agent_name=primary_name, query=request.query, context=context
            ):
                logger.info(f"🔥 API received chunk from agent_client: {chunk[:50]}...")
                yield f"data: {chunk}\n\n"

        except ValueError as e:
            logger.error(f"Agent '{agent_name}' not found: {e}")
            yield f"data: ERROR: {str(e)}\n\n"
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
