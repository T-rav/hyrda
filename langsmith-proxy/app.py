"""
LangSmith-to-Langfuse Proxy

Intercepts LangSmith tracing calls from LangGraph agents and forwards them to Langfuse.
This allows using LangSmith locally for dev while using Langfuse in production.

Usage:
    # Production: Point LangGraph to proxy
    LANGCHAIN_ENDPOINT=http://langsmith-proxy:8002
    LANGCHAIN_API_KEY=dummy  # Proxy doesn't validate

    # Local dev: Use real LangSmith
    LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
    LANGCHAIN_API_KEY=lsv2_pt_your-key
"""

import logging
import os
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Langfuse client
try:
    from langfuse import Langfuse

    langfuse_client = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        debug=os.getenv("LANGFUSE_DEBUG", "false").lower() == "true",
    )
    logger.info("✅ Langfuse client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize Langfuse: {e}")
    langfuse_client = None

app = FastAPI(title="LangSmith to Langfuse Proxy")

# Store run ID mappings (LangSmith run_id -> Langfuse trace/span IDs)
run_id_map: dict[str, dict[str, Any]] = {}


def convert_langsmith_to_langfuse(run_data: dict[str, Any]) -> dict[str, Any]:
    """
    Convert LangSmith run format to Langfuse trace/span format.

    LangSmith format:
        {
            "id": "run-uuid",
            "name": "agent_name",
            "run_type": "chain|llm|tool|retriever",
            "inputs": {...},
            "outputs": {...},
            "start_time": "2024-01-01T00:00:00.000Z",
            "end_time": "2024-01-01T00:00:01.000Z",
            "parent_run_id": "parent-uuid",
            "error": "error message",
            "extra": {...}
        }

    Langfuse format:
        - Root runs become traces
        - Child runs become spans/generations
    """
    run_id = run_data.get("id")
    parent_id = run_data.get("parent_run_id")
    run_type = run_data.get("run_type", "chain")
    name = run_data.get("name", "Unknown")

    # Parse timestamps
    start_time = run_data.get("start_time")
    end_time = run_data.get("end_time")

    if start_time:
        try:
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except Exception:
            start_time = None

    if end_time:
        try:
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except Exception:
            end_time = None

    return {
        "run_id": run_id,
        "parent_id": parent_id,
        "run_type": run_type,
        "name": name,
        "inputs": run_data.get("inputs", {}),
        "outputs": run_data.get("outputs"),
        "start_time": start_time,
        "end_time": end_time,
        "error": run_data.get("error"),
        "metadata": run_data.get("extra", {}),
    }


@app.post("/runs")
async def create_run(request: Request):
    """
    Handle LangSmith run creation.

    Creates Langfuse trace (root) or span (child).
    """
    if not langfuse_client:
        return JSONResponse(
            content={"message": "Langfuse not available"}, status_code=200
        )

    try:
        run_data = await request.json()
        converted = convert_langsmith_to_langfuse(run_data)

        run_id = converted["run_id"]
        parent_id = converted["parent_id"]

        # Root run -> Create Langfuse trace
        if not parent_id:
            trace = langfuse_client.trace(
                id=run_id,
                name=converted["name"],
                input=converted["inputs"],
                output=converted["outputs"],
                metadata={
                    "run_type": converted["run_type"],
                    **converted["metadata"],
                },
            )

            # Store trace reference
            run_id_map[run_id] = {
                "type": "trace",
                "langfuse_id": trace.id,
                "trace": trace,
            }

            logger.info(f"📊 Created Langfuse trace: {converted['name']} ({run_id})")

        # Child run -> Create Langfuse span/generation
        else:
            parent_info = run_id_map.get(parent_id)

            if not parent_info:
                logger.warning(
                    f"⚠️  Parent run {parent_id} not found, creating orphan span"
                )
                # Create as root trace if parent not found
                trace = langfuse_client.trace(
                    id=run_id,
                    name=converted["name"],
                    input=converted["inputs"],
                    output=converted["outputs"],
                )
                run_id_map[run_id] = {"type": "trace", "langfuse_id": trace.id}
            else:
                parent_trace = parent_info.get("trace")

                # LLM calls become generations
                if converted["run_type"] == "llm":
                    generation = parent_trace.generation(
                        id=run_id,
                        name=converted["name"],
                        input=converted["inputs"],
                        output=converted["outputs"],
                        metadata={
                            "run_type": converted["run_type"],
                            **converted["metadata"],
                        },
                    )
                    run_id_map[run_id] = {
                        "type": "generation",
                        "langfuse_id": generation.id,
                        "parent_id": parent_id,
                    }
                    logger.info(
                        f"🤖 Created Langfuse generation: {converted['name']} ({run_id})"
                    )

                # Everything else becomes spans
                else:
                    span = parent_trace.span(
                        id=run_id,
                        name=converted["name"],
                        input=converted["inputs"],
                        output=converted["outputs"],
                        metadata={
                            "run_type": converted["run_type"],
                            **converted["metadata"],
                        },
                    )
                    run_id_map[run_id] = {
                        "type": "span",
                        "langfuse_id": span.id,
                        "parent_id": parent_id,
                        "span": span,
                    }
                    logger.info(
                        f"📍 Created Langfuse span: {converted['name']} ({run_id})"
                    )

        return JSONResponse(content={"id": run_id}, status_code=200)

    except Exception as e:
        logger.error(f"❌ Error creating run: {e}", exc_info=True)
        # Don't fail LangGraph execution, just log and continue
        return JSONResponse(content={"error": str(e)}, status_code=200)


@app.patch("/runs/{run_id}")
async def update_run(run_id: str, request: Request):
    """
    Handle LangSmith run updates (completion, errors, outputs).

    Updates corresponding Langfuse trace/span/generation.
    """
    if not langfuse_client:
        return JSONResponse(content={"message": "Langfuse not available"})

    try:
        update_data = await request.json()
        converted = convert_langsmith_to_langfuse(update_data)

        run_info = run_id_map.get(run_id)

        if not run_info:
            logger.warning(f"⚠️  Run {run_id} not found in map, skipping update")
            return JSONResponse(content={"id": run_id})

        # Update the Langfuse object
        # Note: Langfuse Python SDK auto-updates on object reference
        # We just need to ensure end() is called if run completed

        if converted["end_time"]:
            run_type = run_info["type"]
            logger.info(
                f"✅ Completed Langfuse {run_type}: {converted['name']} ({run_id})"
            )

        if converted["error"]:
            logger.error(
                f"❌ Error in Langfuse run {run_id}: {converted['error']}"
            )

        return JSONResponse(content={"id": run_id})

    except Exception as e:
        logger.error(f"❌ Error updating run: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)})


@app.post("/runs/batch")
async def create_runs_batch(request: Request):
    """Handle batch run creation from LangSmith."""
    if not langfuse_client:
        return JSONResponse(content={"message": "Langfuse not available"})

    try:
        batch_data = await request.json()
        runs = batch_data.get("post", []) + batch_data.get("patch", [])

        results = []
        for run_data in runs:
            # Process each run individually
            converted = convert_langsmith_to_langfuse(run_data)
            results.append({"id": converted["run_id"]})

        logger.info(f"📦 Processed batch of {len(runs)} runs")
        return JSONResponse(content={"results": results})

    except Exception as e:
        logger.error(f"❌ Error processing batch: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "langfuse_available": langfuse_client is not None,
    }


@app.get("/info")
async def info():
    """Proxy info endpoint."""
    return {
        "service": "LangSmith to Langfuse Proxy",
        "version": "1.0.0",
        "langfuse_enabled": langfuse_client is not None,
        "runs_tracked": len(run_id_map),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
