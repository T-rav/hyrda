"""Execution endpoints for embedded agents.

These endpoints actually run the agent code and are called by AgentClient.
They are registered in control plane with endpoint_url pointing here.

Flow:
  User → /agents/{name}/invoke (public API, RBAC checks)
    → AgentClient.invoke()
    → Control Plane (discover endpoint_url)
    → /api/agents/{name}/invoke (THIS FILE - actually runs agent code)
    → Agent implementation (research_agent, help_agent, etc.)
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Router for embedded agent execution (called by AgentClient)
router = APIRouter(
    prefix="/api/agents",
    tags=["embedded-agents"],
)


class EmbeddedAgentRequest(BaseModel):
    """Request for embedded agent execution.

    Security: Called by AgentClient (internal), not directly by users.
    user_id comes from AgentClient's context, which got it from JWT.
    """

    query: str
    context: dict[str, Any] = Field(default_factory=dict)
    # NO user_id field - comes from context dict (populated by AgentClient)


class EmbeddedAgentResponse(BaseModel):
    """Response from embedded agent execution."""

    response: str
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/research/invoke", response_model=EmbeddedAgentResponse)
async def invoke_research_agent(request: EmbeddedAgentRequest):
    """Execute research agent (embedded).

    Called by AgentClient when endpoint_url points to this endpoint.
    """
    logger.info(f"Executing embedded research agent with query: {request.query[:100]}")

    try:
        # Import and instantiate agent
        from agents.system.research.agent_wrapper import ResearchAgentWrapper

        wrapper = ResearchAgentWrapper()

        # Execute agent
        result = await wrapper.invoke(request.query, request.context)

        return EmbeddedAgentResponse(
            response=result.get("response", ""), metadata=result.get("metadata", {})
        )

    except Exception as e:
        logger.error(f"Error executing research agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Research agent execution failed: {str(e)}"
        )


@router.post("/research/stream")
async def stream_research_agent(request: EmbeddedAgentRequest):
    """Stream research agent execution (embedded).

    Called by AgentClient when streaming is requested.
    """
    from fastapi.responses import StreamingResponse

    logger.info(f"Streaming embedded research agent with query: {request.query[:100]}")

    async def event_generator():
        """Generate SSE events from agent execution."""
        try:
            from agents.system.research.agent_wrapper import ResearchAgentWrapper

            wrapper = ResearchAgentWrapper()

            # Check if agent supports streaming
            if not hasattr(wrapper, "stream"):
                # Fallback to non-streaming
                result = await wrapper.invoke(request.query, request.context)
                yield result.get("response", "")
                return

            # Stream agent output
            async for chunk in wrapper.stream(request.query, request.context):
                yield chunk

        except Exception as e:
            logger.error(f"Error streaming research agent: {e}", exc_info=True)
            yield f"ERROR: {str(e)}"

    return StreamingResponse(
        event_generator(),
        media_type="text/plain",  # Raw text, not SSE format (AgentClient handles SSE wrapping)
    )


@router.post("/help/invoke", response_model=EmbeddedAgentResponse)
async def invoke_help_agent(request: EmbeddedAgentRequest):
    """Execute help agent (embedded)."""
    logger.info("Executing embedded help agent")

    try:
        from agents.system.help.agent import HelpAgent

        agent = HelpAgent()
        result = await agent.invoke(request.query, request.context)

        return EmbeddedAgentResponse(
            response=result.get("response", ""), metadata=result.get("metadata", {})
        )

    except Exception as e:
        logger.error(f"Error executing help agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Help agent execution failed: {str(e)}"
        )
