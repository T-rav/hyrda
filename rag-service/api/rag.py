"""RAG API endpoints with request/response models."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from config.settings import get_settings
from dependencies.auth import require_service_auth
from services.agent_client import get_agent_client
from services.llm_service import get_llm_service
from services.routing_service import get_routing_service
from services.vector_service import create_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rag"])


# Request/Response Models


class RAGGenerateRequest(BaseModel):
    """Request model for RAG generation."""

    query: str = Field(..., description="User query")
    conversation_history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Previous conversation messages in format [{'role': 'user', 'content': '...'}, ...]",
    )
    system_message: str | None = Field(None, description="Custom system prompt (overrides default)")
    user_id: str | None = Field(None, description="User ID for tracing and personalization")
    conversation_id: str | None = Field(
        None, description="Conversation ID for tracing (e.g., Slack thread_ts)"
    )
    use_rag: bool = Field(True, description="Enable RAG retrieval from vector database")
    document_content: str | None = Field(
        None, description="Uploaded document content to include in context"
    )
    document_filename: str | None = Field(
        None, description="Uploaded document filename for context"
    )
    session_id: str | None = Field(
        None, description="Session ID for conversation cache (e.g., thread_ts)"
    )
    context: dict[str, Any] | None = Field(
        None, description="Additional context (channel, thread_ts for Slack updates)"
    )


class RAGGenerateResponse(BaseModel):
    """Response model for RAG generation."""

    response: str = Field(..., description="Generated response text")
    citations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Source citations with metadata (title, url, relevance, etc.)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Response metadata (agent_used, rag_used, tools_called, etc.)",
    )


class RAGStatusResponse(BaseModel):
    """Response model for service status."""

    status: str = Field(..., description="Service status (healthy, degraded, unhealthy)")
    vector_enabled: bool = Field(..., description="Vector database enabled")
    llm_provider: str = Field(..., description="LLM provider name")
    embedding_provider: str = Field(..., description="Embedding provider name")
    capabilities: list[str] = Field(..., description="List of enabled capabilities")
    services: dict[str, str] = Field(
        default_factory=dict, description="Status of dependent services"
    )


# Endpoints


# Helper functions for generate_response


def _parse_conversation_metadata(
    x_conversation_metadata: str | None,
) -> tuple[bool, str | None, str]:
    """
    Parse LibreChat conversation metadata from header.

    Args:
        x_conversation_metadata: JSON string with deepSearchEnabled, selectedAgent, researchDepth

    Returns:
        Tuple of (deep_search_enabled, selected_agent, research_depth)
    """
    deep_search_enabled = False
    selected_agent = None
    research_depth = "deep"

    if x_conversation_metadata:
        try:
            metadata = json.loads(x_conversation_metadata)
            deep_search_enabled = metadata.get("deepSearchEnabled", False)
            selected_agent = metadata.get("selectedAgent")
            research_depth = metadata.get("researchDepth", "deep")
            logger.info(
                f"Conversation metadata: deep_search={deep_search_enabled}, "
                f"selected_agent={selected_agent}, research_depth={research_depth}"
            )
        except json.JSONDecodeError:
            logger.warning(f"Invalid conversation metadata JSON: {x_conversation_metadata}")

    return deep_search_enabled, selected_agent, research_depth


def _determine_agent_routing(
    deep_search_enabled: bool,
    selected_agent: str | None,
    query: str,
) -> tuple[str | None, dict[str, Any]]:
    """
    Determine agent routing based on metadata and query patterns.

    Priority:
    1. Deep search enabled → research agent
    2. Agent selected → specific agent
    3. Pattern match → pattern-based agent
    4. None → standard RAG pipeline

    Args:
        deep_search_enabled: Whether deep search toggle is enabled
        selected_agent: Agent name from LibreChat sidebar
        query: User query for pattern matching

    Returns:
        Tuple of (agent_name, agent_context)
    """
    agent_name = None
    agent_context = {}

    # Priority 1: Deep search enabled (routes to research agent)
    if deep_search_enabled:
        agent_name = "research"
        logger.info("Deep search enabled - routing to research agent")

    # Priority 2: Selected agent from LibreChat sidebar
    elif selected_agent:
        agent_name = selected_agent
        logger.info(f"Agent selected via LibreChat - routing to: {selected_agent}")

    # Priority 3: Pattern-based agent detection (existing behavior)
    else:
        routing_service = get_routing_service()
        agent_name = routing_service.detect_agent(query)
        if agent_name:
            logger.info(f"Pattern matched - routing to agent: {agent_name}")

    return agent_name, agent_context


async def _stream_agent_response(
    agent_name: str,
    request: RAGGenerateRequest,
    agent_context: dict[str, Any],
    research_depth: str,
):
    """
    Stream agent execution with SSE format.

    Args:
        agent_name: Name of agent to execute
        request: Original RAG request
        agent_context: Agent-specific context
        research_depth: Research depth for research agent

    Returns:
        StreamingResponse with SSE-formatted agent output
    """
    from fastapi.responses import StreamingResponse

    agent_client = get_agent_client()

    # Build execution context
    context = {
        "user_id": request.user_id,
        "conversation_id": request.conversation_id,
        "session_id": request.session_id,
    }

    # Add agent-specific context
    context.update(agent_context)
    if agent_name == "research":
        context["research_depth"] = research_depth

    # Add document context if provided
    if request.document_content:
        context["document_content"] = request.document_content
        context["document_filename"] = request.document_filename

    # Add Slack context for progress updates
    if request.context:
        context["channel"] = request.context.get("channel")
        context["thread_ts"] = request.context.get("thread_ts")

    async def stream_generator():
        """Generator for SSE-formatted agent chunks."""
        logger.info(f"Starting agent stream: {agent_name}")
        async for chunk in agent_client.stream_agent(
            agent_name=agent_name,
            query=request.query,
            context=context,
        ):
            logger.info(f"Received chunk: {chunk[:50]}")
            yield f"data: {chunk}\n\n"
        logger.info("Agent stream completed")

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _generate_rag_response(
    request: RAGGenerateRequest,
    settings,
) -> RAGGenerateResponse:
    """
    Generate response using standard RAG pipeline (no agent).

    Args:
        request: RAG generation request
        settings: Application settings

    Returns:
        RAGGenerateResponse with generated text and metadata
    """
    logger.info("Processing with RAG pipeline")

    llm_service = get_llm_service()

    # Build messages list from conversation history + current query
    messages = request.conversation_history.copy()
    if not messages or messages[-1]["content"] != request.query:
        messages.append({"role": "user", "content": request.query})

    # Generate response via LLM service
    response_text = await llm_service.get_response(
        messages=messages,
        user_id=request.user_id,
        current_query=request.query,
        document_content=request.document_content,
        document_filename=request.document_filename,
        conversation_id=request.conversation_id,
        conversation_cache=None,
        use_rag=request.use_rag,
        system_message=request.system_message,
    )

    if not response_text:
        raise HTTPException(
            status_code=422,
            detail="Unable to generate response. Query may be empty or invalid.",
        )

    # TODO: Extract citations from context (implement in Phase 2)
    citations = []

    return RAGGenerateResponse(
        response=response_text,
        citations=citations,
        metadata={
            "rag_used": request.use_rag,
            "routed_to_agent": False,
            "vector_db_enabled": settings.vector.enabled,
        },
    )


@router.post("/v1/chat/completions", response_model=RAGGenerateResponse)
@router.post("/chat/completions", response_model=RAGGenerateResponse)
async def generate_response(
    request: RAGGenerateRequest,
    http_request: Request,
    service: dict = Depends(require_service_auth),
    x_conversation_metadata: str | None = Header(None, alias="X-Conversation-Metadata"),
):
    """
    Generate RAG-enhanced response with automatic agent routing.

    This endpoint orchestrates the entire RAG pipeline:
    1. Parses conversation metadata for routing preferences
    2. Determines agent routing (deep search, selected agent, or pattern match)
    3. Routes to agent with streaming if applicable
    4. Falls back to standard RAG pipeline if no agent match

    The endpoint is authenticated via service tokens (bot, control-plane, librechat, etc.).

    Args:
        request: RAG generation request with query and context
        http_request: FastAPI request object (for trace headers)
        service: Service info from authentication (injected by dependency)
        x_conversation_metadata: Optional JSON metadata from LibreChat

    Returns:
        RAGGenerateResponse with generated text, citations, and metadata
        Or StreamingResponse for agent execution

    Raises:
        HTTPException: 500 if generation fails
    """
    service_name = service.get("service", "unknown")
    logger.info(
        f"[{service_name}] RAG request: query='{request.query[:50]}...', "
        f"use_rag={request.use_rag}, conversation_id={request.conversation_id}"
    )

    # Extract or create trace context for unified observability
    from shared.services.langfuse_service import get_langfuse_service
    from shared.utils.trace_propagation import extract_trace_context

    trace_context = extract_trace_context(dict(http_request.headers))
    langfuse_service = get_langfuse_service()

    # If no parent trace context, create root span (standalone entry point)
    if not trace_context and langfuse_service:
        trace_id, root_obs_id = langfuse_service.start_root_span(
            name="rag_service_generate",
            input_data={"query": request.query, "use_rag": request.use_rag},
            metadata={
                "entry_point": "http",
                "service": service_name,
                "conversation_id": request.conversation_id,
            },
        )
        trace_context = {"trace_id": trace_id, "parent_span_id": root_obs_id}
        logger.debug(f"Created root trace: {trace_id}")

    # Store trace context in request state for use by downstream calls
    if trace_context:
        http_request.state.trace_context = trace_context

    try:
        settings = get_settings()

        # Parse metadata from LibreChat
        deep_search_enabled, selected_agent, research_depth = _parse_conversation_metadata(
            x_conversation_metadata
        )

        # Determine routing
        agent_name, agent_context = _determine_agent_routing(
            deep_search_enabled,
            selected_agent,
            request.query,
        )

        # Track usage for LibreChat interactions
        if service_name == "librechat" and request.user_id:
            try:
                from services.usage_tracking_client import get_usage_client

                usage_client = get_usage_client()
                await usage_client.track_librechat_usage(
                    user_id=request.user_id,
                    conversation_id=request.conversation_id or "unknown",
                    agent_used=agent_name,
                    deep_search=str(deep_search_enabled).lower(),
                    interaction_type="agent_message" if agent_name else "rag_message",
                    email=request.user_id,  # LibreChat uses email as user_id
                )
            except Exception as e:
                logger.debug(f"Failed to track LibreChat usage: {e}")

        # Route to agent if applicable
        if agent_name:
            logger.info(f"Routing to agent: {agent_name}")
            return await _stream_agent_response(
                agent_name,
                request,
                agent_context,
                research_depth,
            )

        # Standard RAG pipeline
        return await _generate_rag_response(request, settings)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"RAG generation failed: {str(e)}",
        ) from e


@router.get("/v1/status", response_model=RAGStatusResponse)
@router.get("/status", response_model=RAGStatusResponse)  # Alias
async def get_status(
    service: dict = Depends(require_service_auth),
):
    """
    Get RAG service status and capabilities.

    Returns information about enabled features, provider configurations,
    and health of dependent services.

    Args:
        service: Service info from authentication (injected by dependency)

    Returns:
        RAGStatusResponse with service status and capabilities
    """
    try:
        settings = get_settings()

        capabilities = ["RAG generation"]

        if settings.vector.enabled:
            capabilities.append("Vector search")

        if settings.rag.enable_query_rewriting:
            capabilities.append("Query rewriting")

        if settings.search.tavily_api_key:
            capabilities.append("Web search (Tavily)")

        if settings.search.perplexity_enabled and settings.search.perplexity_api_key:
            capabilities.append("Deep research (Perplexity)")

        # Check service health
        services_status = {}

        # Check vector DB
        if settings.vector.enabled:
            try:
                vector_store = create_vector_store(settings.vector)
                collection_info = await vector_store.get_collection_info()
                services_status["vector_db"] = "healthy" if collection_info else "degraded"
            except Exception as e:
                logger.warning(f"Vector DB status check failed: {e}")
                services_status["vector_db"] = "unhealthy"

        # Check agent-service connectivity
        try:
            agent_client = get_agent_client()
            # Simple connectivity check
            agents = await agent_client.list_agents()
            services_status["agent_service"] = "healthy" if agents else "degraded"
        except Exception as e:
            logger.warning(f"Agent service status check failed: {e}")
            services_status["agent_service"] = "unhealthy"

        # Determine overall status
        if all(status == "healthy" for status in services_status.values()):
            overall_status = "healthy"
        elif any(status == "unhealthy" for status in services_status.values()):
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return RAGStatusResponse(
            status=overall_status,
            vector_enabled=settings.vector.enabled,
            llm_provider=settings.llm.provider,
            embedding_provider=settings.embedding.provider,
            capabilities=capabilities,
            services=services_status,
        )

    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Status check failed: {str(e)}",
        ) from e
