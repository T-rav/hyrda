"""RAG API endpoints with request/response models."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
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


@router.post("/v1/chat/completions", response_model=RAGGenerateResponse)
@router.post("/chat/completions", response_model=RAGGenerateResponse)  # Alias without v1
async def generate_response(
    request: RAGGenerateRequest,
    service: dict = Depends(require_service_auth),
):
    """
    Generate RAG-enhanced response with automatic agent routing.

    This endpoint orchestrates the entire RAG pipeline:
    1. Checks if query needs agent routing (e.g., /profile, /research commands)
    2. If agent needed: Routes to agent-service
    3. If not: Performs RAG retrieval and LLM generation with tools
    4. Returns response with citations and metadata

    The endpoint is authenticated via service tokens (bot, control-plane, etc.).

    Args:
        request: RAG generation request with query and context
        service: Service info from authentication (injected by dependency)

    Returns:
        RAGGenerateResponse with generated text, citations, and metadata

    Raises:
        HTTPException: 500 if generation fails
    """
    service_name = service.get("service", "unknown")
    logger.info(
        f"[{service_name}] RAG generate request: query='{request.query[:50]}...', "
        f"use_rag={request.use_rag}, conversation_id={request.conversation_id}"
    )

    try:
        settings = get_settings()

        # Step 1: Check if query needs agent routing
        routing_service = get_routing_service()
        agent_name = routing_service.detect_agent(request.query)

        if agent_name:
            logger.info(f"Routing to agent: {agent_name}")

            # Route to agent-service
            agent_client = get_agent_client()
            context = {
                "user_id": request.user_id,
                "conversation_id": request.conversation_id,
                "session_id": request.session_id,
            }

            # Add document context if provided
            if request.document_content:
                context["document_content"] = request.document_content
                context["document_filename"] = request.document_filename

            # Use streaming for agents to provide progress updates
            logger.info(f"Streaming agent '{agent_name}' for real-time progress updates")

            from fastapi.responses import StreamingResponse

            async def stream_agent_with_context():
                """Stream agent execution with Slack context for progress updates."""
                # Add Slack context for agent to send updates
                context["channel"] = request.context.get("channel") if request.context else None
                context["thread_ts"] = request.context.get("thread_ts") if request.context else None

                logger.info("💥 stream_agent_with_context starting to consume agent_client.stream_agent")
                async for chunk in agent_client.stream_agent(
                    agent_name=agent_name,
                    query=request.query,
                    context=context,
                ):
                    logger.info(f"💥 RAG API received chunk: {chunk[:50]}")
                    # Wrap in SSE format for bot to consume
                    yield f"data: {chunk}\n\n"
                logger.info("💥 stream_agent_with_context finished")

            return StreamingResponse(
                stream_agent_with_context(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable nginx buffering
                },
            )

        # Step 2: RAG generation (no agent needed)
        logger.info("Processing with RAG pipeline")

        llm_service = get_llm_service()

        # Build messages list from conversation history + current query
        messages = request.conversation_history.copy()
        if not messages or messages[-1]["content"] != request.query:
            # Add current query if not already last message
            messages.append({"role": "user", "content": request.query})

        # Generate response via LLM service
        response_text = await llm_service.get_response(
            messages=messages,
            user_id=request.user_id,
            current_query=request.query,
            document_content=request.document_content,
            document_filename=request.document_filename,
            conversation_id=request.conversation_id,
            conversation_cache=None,  # Cache handled internally by llm_service
            use_rag=request.use_rag,
        )

        # Handle empty/invalid responses
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

    except HTTPException:
        # Re-raise HTTPExceptions (validation errors, etc.)
        raise
    except Exception as e:
        logger.error(f"RAG generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"RAG generation failed: {str(e)}",
        )


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
        )
