"""
LangSmith-to-Langfuse Proxy

Intercepts LangSmith tracing calls from LangGraph agents and forwards them to Langfuse.
This allows using LangSmith locally for dev while using Langfuse in production.

Usage:
    # Production: Point LangGraph to proxy
    LANGCHAIN_ENDPOINT=http://langsmith-proxy:8002
    PROXY_API_KEY=your-secure-proxy-key  # Set in proxy .env
    LANGCHAIN_API_KEY=your-secure-proxy-key  # Set in agent .env

    # Local dev: Use real LangSmith
    LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
    LANGCHAIN_API_KEY=lsv2_pt_your-real-langsmith-key
"""

import logging
import os
import secrets
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security: API key validation
security = HTTPBearer()
PROXY_API_KEY = os.getenv("PROXY_API_KEY", "")

if not PROXY_API_KEY:
    # Generate a random key if not set (for dev/testing)
    PROXY_API_KEY = secrets.token_urlsafe(32)
    logger.warning(f"⚠️  No PROXY_API_KEY set! Generated temporary key: {PROXY_API_KEY}")
    logger.warning("⚠️  Set PROXY_API_KEY in .env for production!")
else:
    logger.info("✅ PROXY_API_KEY configured")

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


def validate_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> bool:
    """
    Validate API key from Authorization header.

    Expects: Authorization: Bearer <api-key>
    """
    if not credentials:
        logger.warning("❌ Missing Authorization header")
        raise HTTPException(status_code=401, detail="Missing API key")

    provided_key = credentials.credentials

    if provided_key != PROXY_API_KEY:
        logger.warning(f"❌ Invalid API key provided: {provided_key[:8]}...")
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True


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
async def create_run(request: Request, authorized: bool = Depends(validate_api_key)):
    """
    Handle LangSmith run creation.

    Creates Langfuse trace (root) or span (child).

    Requires: Authorization: Bearer <proxy-api-key>
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

        # Root run -> Create Langfuse observation (trace)
        if not parent_id:
            # Use start_observation for Langfuse SDK 3.x (creates trace-level observation)
            # Reuse LangSmith trace ID for easy cross-reference (remove dashes for Langfuse)
            trace_id_no_dashes = run_id.replace("-", "")
            obs_data = {
                "trace_context": {"trace_id": trace_id_no_dashes},  # Reuse LangSmith trace ID (no dashes)
                "name": converted["name"],
                "input": converted["inputs"],
                "metadata": {
                    "run_type": converted["run_type"],
                    "langsmith_trace": True,
                    "langsmith_id": run_id,  # Store original LangSmith ID in metadata
                    "langsmith_trace_id_dashes": run_id,  # Also store with dashes for search
                    "agent_name": converted["name"],  # Agent name for filtering
                    **converted["metadata"],
                },
            }

            # Add output if available
            if converted["outputs"]:
                obs_data["output"] = converted["outputs"]

            # Note: Timestamps are managed by the SDK, not passed in
            # The SDK handles start_time automatically on creation
            # end_time is set when calling .end() method

            # Create observation (this acts as trace root in SDK 3.x)
            observation = langfuse_client.start_observation(**obs_data)

            # Store reference for child spans (use Langfuse's auto-generated observation ID)
            run_id_map[run_id] = {
                "type": "observation",
                "langfuse_id": observation.id,  # Langfuse observation ID (16 hex chars for parent refs)
                "observation": observation,
            }

            logger.info(f"📊 Created Langfuse trace: {converted['name']} (langsmith_id={run_id}, langfuse_trace_id={trace_id_no_dashes}, observation_id={observation.id})")

        # Child run -> Create Langfuse span/generation
        else:
            parent_info = run_id_map.get(parent_id)

            if not parent_info:
                logger.warning(
                    f"⚠️  Parent run {parent_id} not found, creating orphan observation"
                )
                # Create as root observation if parent not found
                obs = langfuse_client.start_observation(
                    name=converted["name"],
                    input=converted["inputs"],
                    output=converted["outputs"],
                    metadata={"langsmith_id": run_id},
                )
                run_id_map[run_id] = {
                    "type": "observation",
                    "langfuse_id": run_id,
                    "observation": obs,
                }
            else:
                parent_obs = parent_info.get("observation")
                parent_langfuse_id = parent_info.get("langfuse_id", parent_id)

                # Get the root trace ID (walk up to find root)
                root_trace_id = parent_langfuse_id
                current_parent = parent_info
                current_parent_id = current_parent.get("parent_id")

                while current_parent_id:
                    parent_parent_info = run_id_map.get(current_parent_id)
                    if parent_parent_info:
                        root_trace_id = parent_parent_info.get("langfuse_id", root_trace_id)
                        current_parent = parent_parent_info
                        current_parent_id = current_parent.get("parent_id")
                    else:
                        break

                # Remove dashes from trace ID for Langfuse
                root_trace_id_no_dashes = str(root_trace_id).replace("-", "")

                # LLM calls become generations
                if converted["run_type"] == "llm":
                    gen_data = {
                        "trace_context": {
                            "trace_id": root_trace_id_no_dashes,
                            "parent_span_id": parent_langfuse_id  # Already 16 hex chars from Langfuse
                        },
                        "name": converted["name"],
                        "input": converted["inputs"],
                        "metadata": {
                            "run_type": converted["run_type"],
                            "langsmith_id": run_id,
                            "parent_langsmith_id": parent_id,
                            **converted["metadata"],
                        },
                    }
                    if converted["outputs"]:
                        gen_data["output"] = converted["outputs"]

                    # Note: SDK handles timestamps automatically

                    # Use start_generation method
                    generation = langfuse_client.start_generation(**gen_data)

                    run_id_map[run_id] = {
                        "type": "generation",
                        "langfuse_id": generation.id,  # Use Langfuse generation ID
                        "parent_id": parent_id,
                        "generation": generation,
                    }
                    logger.info(
                        f"🤖 Created Langfuse generation: {converted['name']} (langsmith_id={run_id}, langfuse_id={generation.id})"
                    )

                # Everything else becomes spans
                else:
                    span_data = {
                        "trace_context": {
                            "trace_id": root_trace_id_no_dashes,
                            "parent_span_id": parent_langfuse_id  # Already 16 hex chars from Langfuse
                        },
                        "name": converted["name"],
                        "input": converted["inputs"],
                        "metadata": {
                            "run_type": converted["run_type"],
                            "langsmith_id": run_id,
                            "parent_langsmith_id": parent_id,
                            **converted["metadata"],
                        },
                    }
                    if converted["outputs"]:
                        span_data["output"] = converted["outputs"]

                    # Note: SDK handles timestamps automatically

                    # Use start_span method
                    span = langfuse_client.start_span(**span_data)

                    run_id_map[run_id] = {
                        "type": "span",
                        "langfuse_id": span.id,  # Use Langfuse span ID
                        "parent_id": parent_id,
                        "span": span,
                    }
                    logger.info(
                        f"📍 Created Langfuse span: {converted['name']} (langsmith_id={run_id}, langfuse_id={span.id})"
                    )

        return JSONResponse(content={"id": run_id}, status_code=200)

    except Exception as e:
        logger.error(f"❌ Error creating run: {e}", exc_info=True)
        # Don't fail LangGraph execution, just log and continue
        return JSONResponse(content={"error": str(e)}, status_code=200)


@app.patch("/runs/{run_id}")
async def update_run(
    run_id: str, request: Request, authorized: bool = Depends(validate_api_key)
):
    """
    Handle LangSmith run updates (completion, errors, outputs).

    Updates corresponding Langfuse trace/span/generation.

    Requires: Authorization: Bearer <proxy-api-key>
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

        # Update the Langfuse observation/span/generation with completion data
        run_type = run_info["type"]
        obj = run_info.get(run_type)  # Get the actual Langfuse object

        if obj and hasattr(obj, "end"):
            # Update observation with outputs/errors, then end it
            try:
                # Update with output, level, status_message if available
                update_params = {}
                if converted["outputs"]:
                    update_params["output"] = converted["outputs"]
                if converted["error"]:
                    update_params["level"] = "ERROR"
                    update_params["status_message"] = converted["error"]

                if update_params:
                    obj.update(**update_params)

                # End the observation (only accepts end_time parameter)
                if converted["end_time"]:
                    # Convert datetime to nanoseconds since epoch if needed
                    obj.end()
                else:
                    obj.end()

                logger.info(
                    f"✅ Completed Langfuse {run_type}: {converted['name']} ({run_id})"
                )
            except Exception as e:
                logger.error(f"Error ending {run_type}: {e}")

        if converted["error"]:
            logger.error(f"❌ Error in Langfuse run {run_id}: {converted['error']}")

        # Flush to Langfuse after completion of root trace
        if converted["end_time"] and not run_info.get("parent_id"):
            # Root trace completed, flush to Langfuse
            langfuse_client.flush()
            logger.info(f"📤 Flushed trace to Langfuse: {run_id}")

        return JSONResponse(content={"id": run_id})

    except Exception as e:
        logger.error(f"❌ Error updating run: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)})


@app.post("/runs/batch")
async def create_runs_batch(request: Request):
    """
    Handle batch run creation from LangSmith.

    Note: LangSmith SDK doesn't send Authorization header in batch requests.
    For production, secure via network policies (internal service-to-service only).
    """
    logger.info("📦 Batch request received")

    if not langfuse_client:
        return JSONResponse(content={"message": "Langfuse not available"})

    try:
        batch_data = await request.json()
        post_runs = batch_data.get("post", [])
        patch_runs = batch_data.get("patch", [])

        # Process POST (create) runs
        for run_data in post_runs:
            try:
                converted = convert_langsmith_to_langfuse(run_data)
                run_id = converted["run_id"]
                parent_id = converted["parent_id"]

                # Root run -> Create Langfuse observation
                if not parent_id:
                    trace_id_no_dashes = run_id.replace("-", "")
                    obs_data = {
                        "trace_context": {"trace_id": trace_id_no_dashes},  # Reuse LangSmith trace ID (no dashes)
                        "name": converted["name"],
                        "input": converted["inputs"],
                        "metadata": {
                            "run_type": converted["run_type"],
                            "langsmith_trace": True,
                            "langsmith_id": run_id,
                            "langsmith_trace_id_dashes": run_id,  # Store with dashes for search
                            "agent_name": converted["name"],  # Agent name for filtering
                            **converted["metadata"],
                        },
                    }
                    if converted["outputs"]:
                        obs_data["output"] = converted["outputs"]

                    observation = langfuse_client.start_observation(**obs_data)
                    run_id_map[run_id] = {
                        "type": "observation",
                        "langfuse_id": observation.id,  # Use Langfuse observation ID
                        "observation": observation,
                    }
                    logger.info(f"📊 Batch created trace: {converted['name']} (langsmith_id={run_id}, langfuse_trace_id={trace_id_no_dashes}, observation_id={observation.id})")

                # Child run -> Create span/generation
                else:
                    parent_info = run_id_map.get(parent_id)
                    if not parent_info:
                        logger.warning(f"⚠️  Parent {parent_id} not found in batch")
                        continue

                    # Get parent and root trace IDs
                    parent_langfuse_id = parent_info.get("langfuse_id", parent_id)
                    root_trace_id = parent_langfuse_id
                    current_parent = parent_info
                    current_parent_id = current_parent.get("parent_id")

                    while current_parent_id:
                        parent_parent_info = run_id_map.get(current_parent_id)
                        if parent_parent_info:
                            root_trace_id = parent_parent_info.get("langfuse_id", root_trace_id)
                            current_parent = parent_parent_info
                            current_parent_id = current_parent.get("parent_id")
                        else:
                            break

                    root_trace_id_no_dashes = str(root_trace_id).replace("-", "")

                    if converted["run_type"] == "llm":
                        gen_data = {
                            "trace_context": {
                                "trace_id": root_trace_id_no_dashes,
                                "parent_span_id": parent_langfuse_id  # Already 16 hex chars
                            },
                            "name": converted["name"],
                            "input": converted["inputs"],
                            "metadata": {
                                "run_type": converted["run_type"],
                                "langsmith_id": run_id,
                                "parent_langsmith_id": parent_id,
                                **converted["metadata"],
                            },
                        }
                        if converted["outputs"]:
                            gen_data["output"] = converted["outputs"]

                        generation = langfuse_client.start_generation(**gen_data)
                        run_id_map[run_id] = {
                            "type": "generation",
                            "langfuse_id": generation.id,  # Use Langfuse generation ID
                            "parent_id": parent_id,
                            "generation": generation,
                        }
                        logger.info(f"🤖 Batch created generation: {converted['name']} (langsmith_id={run_id}, langfuse_id={generation.id})")
                    else:
                        span_data = {
                            "trace_context": {
                                "trace_id": root_trace_id_no_dashes,
                                "parent_span_id": parent_langfuse_id  # Already 16 hex chars
                            },
                            "name": converted["name"],
                            "input": converted["inputs"],
                            "metadata": {
                                "run_type": converted["run_type"],
                                "langsmith_id": run_id,
                                "parent_langsmith_id": parent_id,
                                **converted["metadata"],
                            },
                        }
                        if converted["outputs"]:
                            span_data["output"] = converted["outputs"]

                        span = langfuse_client.start_span(**span_data)
                        run_id_map[run_id] = {
                            "type": "span",
                            "langfuse_id": span.id,  # Use Langfuse span ID
                            "parent_id": parent_id,
                            "span": span,
                        }
                        logger.info(f"📍 Batch created span: {converted['name']} (langsmith_id={run_id}, langfuse_id={span.id})")

            except Exception as e:
                logger.error(f"❌ Error processing batch POST run: {e}")

        # Process PATCH (update) runs
        for run_data in patch_runs:
            try:
                converted = convert_langsmith_to_langfuse(run_data)
                run_id = converted["run_id"]
                run_info = run_id_map.get(run_id)

                if not run_info:
                    logger.warning(f"⚠️  Run {run_id} not found in batch update")
                    continue

                run_type = run_info["type"]
                obj = run_info.get(run_type)

                if obj and hasattr(obj, "end"):
                    # Update with output, level, status_message if available
                    update_params = {}
                    if converted["outputs"]:
                        update_params["output"] = converted["outputs"]
                    if converted["error"]:
                        update_params["level"] = "ERROR"
                        update_params["status_message"] = converted["error"]

                    if update_params:
                        obj.update(**update_params)

                    # End the observation (only accepts end_time parameter)
                    obj.end()

                    logger.info(f"✅ Batch completed {run_type}: {run_id}")

            except Exception as e:
                logger.error(f"❌ Error processing batch PATCH run: {e}")

        # Flush after batch processing
        langfuse_client.flush()
        logger.info(f"📦 Processed batch: {len(post_runs)} creates, {len(patch_runs)} updates")

        return JSONResponse(content={"message": "Batch processed"})

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


@app.on_event("shutdown")
async def shutdown_event():
    """Flush any remaining traces to Langfuse on shutdown."""
    if langfuse_client:
        logger.info("📤 Flushing remaining traces to Langfuse...")
        langfuse_client.flush()
        logger.info("✅ Shutdown complete")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8003"))
    uvicorn.run(app, host="0.0.0.0", port=port)
