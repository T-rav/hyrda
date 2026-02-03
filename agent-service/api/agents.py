"""Agent execution API endpoints."""

import logging
import os
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
    """List all available agents from control plane.

    Returns:
        List of agent names and their metadata
    """
    import os

    import httpx

    control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control-plane:6001")
    service_token = os.getenv("AGENT_SERVICE_TOKEN", "dev-agent-service-token")

    try:
        async with httpx.AsyncClient(verify=False) as client:  # nosec B501 - Internal Docker network with self-signed certs
            response = await client.get(
                f"{control_plane_url}/api/agents",
                headers={"X-Service-Token": service_token},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
            agents = data.get("agents", [])

        return AgentListResponse(
            agents=[
                {
                    "name": agent.get("name"),
                    "aliases": agent.get("aliases", []),
                    "description": agent.get("description", "No description"),
                }
                for agent in agents
            ]
        )
    except Exception as e:
        logger.error(f"Failed to list agents from control plane: {e}", exc_info=True)
        raise HTTPException(
            status_code=503, detail="Failed to retrieve agents from control plane"
        )


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

    # Extract user identity from JWT, service account, or service token (NEVER from request body!)
    user_id = None
    auth_type = None
    service_account_name = None

    # Try JWT first (end user request)
    auth_header = http_request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and not auth_header[7:].startswith("sa_"):
        try:
            from dependencies.auth import get_current_user

            user_info = await get_current_user(http_request)
            user_id = user_info["user_id"]
            auth_type = "jwt"
            logger.info(f"User {user_id} authenticated via JWT")
        except HTTPException:
            logger.debug(
                "JWT authentication failed, trying next method"
            )  # Not a valid JWT, try next method

    # Try service account API key (external API integration)
    if not auth_type:
        from dependencies.service_account_auth import verify_service_account_api_key

        try:
            service_account = await verify_service_account_api_key(http_request)
            if service_account:
                auth_type = "service_account"
                service_account_name = service_account.name

                # System agents are for Slack users only, not external API integrations
                if agent_info.get("is_system", False):
                    logger.warning(
                        f"Service account '{service_account_name}' attempted to access "
                        f"system agent '{primary_name}' (forbidden)"
                    )
                    raise HTTPException(
                        status_code=403,
                        detail=f"System agent '{agent_name}' is only available to Slack users, not API keys",
                    )

                # Check if this agent is allowed for this service account
                if service_account.allowed_agents is not None:
                    # Specific agents allowed - check if current agent is in list
                    if primary_name not in service_account.allowed_agents:
                        logger.warning(
                            f"Service account '{service_account_name}' attempted to access "
                            f"unauthorized agent '{primary_name}'"
                        )
                        raise HTTPException(
                            status_code=403,
                            detail=f"Service account not authorized to access agent '{agent_name}'",
                        )

                # Check if service account has invoke scope
                if "agents:invoke" not in service_account.scopes:
                    logger.warning(
                        f"Service account '{service_account_name}' lacks agents:invoke scope"
                    )
                    raise HTTPException(
                        status_code=403,
                        detail="Service account does not have agents:invoke permission",
                    )

                logger.info(
                    f"Service account '{service_account_name}' authenticated for agent '{primary_name}'"
                )
                # Service accounts don't have user_id
                user_id = None
        except HTTPException:
            # Service account validation failed - re-raise
            raise

    # Try internal service token (bot, librechat, tasks)
    if not auth_type:
        from shared.utils.service_auth import verify_service_token

        service_token = http_request.headers.get("X-Service-Token")
        service_info = verify_service_token(service_token) if service_token else None

        if service_info:
            auth_type = "service"
            service_name = service_info.get("service", "unknown")
            logger.info(f"Authenticated as internal service: {service_name}")
            # Service can optionally forward user context (trusted)
            user_id = http_request.headers.get("X-User-Context")
        else:
            # No valid auth
            raise HTTPException(
                status_code=401,
                detail="Authentication required: provide JWT token, service account API key, or service token",
            )

    # Check user permissions if user_id extracted from JWT (user request)
    if user_id and auth_type == "jwt":
        import httpx

        control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control-plane:6001")
        permissions_url = f"{control_plane_url}/api/users/{user_id}/permissions"

        # Use service token for service-to-service auth (agent-service → control-plane)
        service_token = os.getenv("AGENT_SERVICE_TOKEN", "dev-agent-service-token")
        headers = {"X-Service-Token": service_token}

        try:
            async with httpx.AsyncClient(verify=False) as client:  # nosec B501 - Internal Docker network with self-signed certs
                perm_response = await client.get(
                    permissions_url, headers=headers, timeout=5.0
                )

                if perm_response.status_code == 200:
                    perm_data = perm_response.json()
                    permissions = (
                        perm_data.get("permissions", [])
                        if isinstance(perm_data, dict)
                        else perm_data
                    )

                    # Check if user has permission for this specific agent
                    # Accept EITHER the primary name OR any alias (permissions may be granted by alias)
                    agent_names = [
                        p.get("agent_name") for p in permissions if isinstance(p, dict)
                    ]

                    logger.info(
                        f"User {user_id} permissions: {agent_names}, checking for: {primary_name}"
                    )

                    # Check if user has permission for the primary name OR the requested name (alias)
                    has_permission = (
                        primary_name in agent_names or agent_name.lower() in agent_names
                    )

                    if not has_permission:
                        raise HTTPException(
                            status_code=403,
                            detail=f"User {user_id} does not have permission to invoke agent '{primary_name}'",
                        )
                else:
                    # If we can't get permissions, deny access (fail closed)
                    raise HTTPException(
                        status_code=403, detail="Could not verify user permissions"
                    )
        except httpx.RequestError as e:
            # If control-plane is unavailable, deny access (fail closed)
            logger.error(f"Error checking permissions: {e}")
            raise HTTPException(
                status_code=503, detail="Permission service unavailable"
            )

    logger.info(
        f"Invoking agent '{agent_name}' (auth: {auth_type}, user: {user_id or 'none'})"
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
                "auth_type": auth_type,
                "user_id": user_id,
                "service_account": service_account_name,
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
        if user_id:
            context["user_id"] = user_id

        # Add auth metadata for audit trail
        context["auth_type"] = auth_type

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

    # Extract user identity from JWT, service account, or service token (NEVER from request body!)
    user_id = None
    auth_type = None
    service_account_name = None

    # Try JWT first (end user request)
    auth_header = http_request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and not auth_header[7:].startswith("sa_"):
        try:
            from dependencies.auth import get_current_user

            user_info = await get_current_user(http_request)
            user_id = user_info["user_id"]
            auth_type = "jwt"
            logger.info(f"User {user_id} authenticated via JWT for streaming")
        except HTTPException:
            logger.debug(
                "JWT authentication failed for streaming, trying next method"
            )  # Not a valid JWT, try next method

    # Try service account API key (external API integration)
    if not auth_type:
        from dependencies.service_account_auth import verify_service_account_api_key

        try:
            service_account = await verify_service_account_api_key(http_request)
            if service_account:
                auth_type = "service_account"
                service_account_name = service_account.name

                # System agents are for Slack users only, not external API integrations
                if agent_info.get("is_system", False):
                    logger.warning(
                        f"Service account '{service_account_name}' attempted to access "
                        f"system agent '{primary_name}' (forbidden)"
                    )
                    raise HTTPException(
                        status_code=403,
                        detail=f"System agent '{agent_name}' is only available to Slack users, not API keys",
                    )

                # Check if this agent is allowed for this service account
                if service_account.allowed_agents is not None:
                    if primary_name not in service_account.allowed_agents:
                        logger.warning(
                            f"Service account '{service_account_name}' attempted to access "
                            f"unauthorized agent '{primary_name}' (streaming)"
                        )
                        raise HTTPException(
                            status_code=403,
                            detail=f"Service account not authorized to access agent '{agent_name}'",
                        )

                # Check if service account has invoke scope
                if "agents:invoke" not in service_account.scopes:
                    logger.warning(
                        f"Service account '{service_account_name}' lacks agents:invoke scope (streaming)"
                    )
                    raise HTTPException(
                        status_code=403,
                        detail="Service account does not have agents:invoke permission",
                    )

                logger.info(
                    f"Service account '{service_account_name}' authenticated for streaming agent '{primary_name}'"
                )
                user_id = None
        except HTTPException:
            raise

    # Try internal service token (bot, librechat, tasks)
    if not auth_type:
        from shared.utils.service_auth import verify_service_token

        service_token = http_request.headers.get("X-Service-Token")
        service_info = verify_service_token(service_token) if service_token else None

        if service_info:
            auth_type = "service"
            service_name = service_info.get("service", "unknown")
            logger.info(
                f"Authenticated as internal service for streaming: {service_name}"
            )
            user_id = http_request.headers.get("X-User-Context")
        else:
            raise HTTPException(
                status_code=401,
                detail="Authentication required: provide JWT token, service account API key, or service token",
            )

    # Check user permissions if user_id extracted from JWT (user request)
    if user_id and auth_type == "jwt":
        import httpx

        control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control-plane:6001")
        permissions_url = f"{control_plane_url}/api/users/{user_id}/permissions"

        # Use service token for service-to-service auth
        service_token = os.getenv("AGENT_SERVICE_TOKEN", "dev-agent-service-token")
        headers = {"X-Service-Token": service_token}

        try:
            async with httpx.AsyncClient(verify=False) as client:  # nosec B501 - Internal Docker network with self-signed certs
                perm_response = await client.get(
                    permissions_url, headers=headers, timeout=5.0
                )

                if perm_response.status_code == 200:
                    perm_data = perm_response.json()
                    permissions = (
                        perm_data.get("permissions", [])
                        if isinstance(perm_data, dict)
                        else perm_data
                    )

                    agent_names = [
                        p.get("agent_name") for p in permissions if isinstance(p, dict)
                    ]
                    has_permission = (
                        primary_name in agent_names or agent_name.lower() in agent_names
                    )

                    if not has_permission:
                        raise HTTPException(
                            status_code=403,
                            detail=f"User {user_id} does not have permission to invoke agent '{primary_name}'",
                        )
                else:
                    raise HTTPException(
                        status_code=403, detail="Could not verify user permissions"
                    )
        except httpx.RequestError as e:
            logger.error(f"Error checking permissions: {e}")
            raise HTTPException(
                status_code=503, detail="Permission service unavailable"
            )

    logger.info(
        f"Streaming agent '{agent_name}' (auth: {auth_type}, user: {user_id or 'none'})"
    )

    async def event_generator():
        """Generate server-sent events from agent execution via HTTP."""
        try:
            # Stream agent output via AgentClient (HTTP-only)
            context = request.context.copy()

            # Add user_id to context (from JWT/service token, NEVER from request body!)
            if user_id:
                context["user_id"] = user_id

            # Add auth metadata for audit trail
            context["auth_type"] = auth_type

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
