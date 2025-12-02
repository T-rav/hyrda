"""Agent management endpoints - FastAPI version."""

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from models import AgentGroupPermission, AgentMetadata, AgentPermission, get_db_session
from sqlalchemy import func
from utils.audit import AuditAction, log_agent_action
from utils.errors import error_response, success_response
from utils.idempotency import require_idempotency
from utils.pagination import build_pagination_response, get_pagination_params, paginate_query
from utils.permissions import require_admin
from utils.validation import validate_agent_name, validate_display_name

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def list_agents(request: Request) -> dict[str, Any]:
    """List all registered agents from database.

    Agents are now stored in the database (agent_metadata table) and can be
    configured dynamically without code changes. Bot and agent-service query
    this endpoint to discover available agents.

    Query params:
        include_deleted: If "true", include soft-deleted agents (default: false)
        page: Page number (1-indexed, default: 1)
        per_page: Items per page (default: 50, max: 100)
    """
    try:
        # Check if we should include deleted agents
        include_deleted = request.query_params.get("include_deleted", "false").lower() == "true"

        # Get pagination parameters - pass request for query params
        page, per_page = get_pagination_params(request, default_per_page=50, max_per_page=100)

        with get_db_session() as session:
            # Get agents from database, filtering deleted by default
            query = session.query(AgentMetadata).order_by(AgentMetadata.agent_name)
            if not include_deleted:
                query = query.filter(~AgentMetadata.is_deleted)

            # Paginate query
            agents, total_count = paginate_query(query, page, per_page)

            # Batch load group counts for all agents in ONE query using GROUP BY
            # This prevents N+1 query problem
            agent_names = [a.agent_name for a in agents]
            group_counts_query = session.query(
                AgentGroupPermission.agent_name,
                func.count(AgentGroupPermission.id)
            ).filter(
                AgentGroupPermission.agent_name.in_(agent_names)
            ).group_by(AgentGroupPermission.agent_name).all()

            # Build lookup dictionary: agent_name -> count
            group_counts = dict(group_counts_query)

            # Build agent data using cached counts
            agents_data = []
            for agent in agents:
                group_count = group_counts.get(agent.agent_name, 0)

                agents_data.append({
                    "name": agent.agent_name,
                    "display_name": agent.display_name,
                    "aliases": agent.get_aliases(),
                    "description": agent.description or "No description",
                    "is_public": agent.is_public,
                    "requires_admin": agent.requires_admin,
                    "is_system": agent.is_system,
                    "is_deleted": agent.is_deleted,
                    "authorized_groups": group_count,
                })

            # Build paginated response
            response = build_pagination_response(agents_data, total_count, page, per_page)
            # Keep "agents" key for backward compatibility
            return {"agents": response["items"], "pagination": response["pagination"]}

    except Exception as e:
        logger.error(f"Error listing agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"})


@router.post("/register")
@require_idempotency(ttl_hours=24)
async def register_agent(request: Request) -> dict[str, Any]:
    """Register or update an agent in the database.

    Called by agent-service on startup to sync available agents.
    Upserts agent metadata - creates if doesn't exist, updates if it does.

    Headers:
        Idempotency-Key: Optional unique key to prevent duplicate registrations
    """
    try:
        data = await request.json()
        agent_name = data.get("name")
        display_name = data.get("display_name", agent_name)
        description = data.get("description", "")
        aliases = data.get("aliases", [])
        is_system = data.get("is_system", False)

        # Validate agent name
        is_valid, error_msg = validate_agent_name(agent_name)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail={"error": error_msg, "error_code": "VALIDATION_ERROR"}
            )

        # Validate display name (optional)
        is_valid, error_msg = validate_display_name(display_name)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail={"error": error_msg, "error_code": "VALIDATION_ERROR"}
            )

        with get_db_session() as session:
            # Use explicit transaction to ensure lock is properly held
            with session.begin():
                # Check if agent exists (deleted or not)
                # Use row-level locking to prevent race conditions
                agent = session.query(AgentMetadata).filter(
                    AgentMetadata.agent_name == agent_name
                ).with_for_update().first()

                # Validate uniqueness: ensure no non-deleted agent with same name exists
                if agent and agent.is_deleted:
                    # Before reactivating, double-check no active agent with same name exists
                    existing_active = session.query(AgentMetadata).filter(
                        AgentMetadata.agent_name == agent_name,
                        AgentMetadata.is_deleted == False
                    ).first()
                    if existing_active:
                        raise HTTPException(
                            status_code=409,
                            detail={"error": f"Agent '{agent_name}' already exists", "error_code": "AGENT_EXISTS"}
                        )

                # Check for conflict: non-deleted agent with same name
                if agent and not agent.is_deleted:
                    # Update existing active agent
                    agent.display_name = display_name
                    agent.description = description
                    agent.set_aliases(aliases)
                    agent.is_system = is_system
                    logger.info(f"Updated agent '{agent_name}' in database")
                    action = "updated"
                elif agent and agent.is_deleted:
                    # Reactivate deleted agent (undelete and update)
                    agent.is_deleted = False
                    agent.is_public = True  # Re-enable when reactivating
                    agent.display_name = display_name
                    agent.description = description
                    agent.set_aliases(aliases)
                    agent.is_system = is_system
                    logger.info(f"Reactivated deleted agent '{agent_name}'")
                    action = "reactivated"
                else:
                    # Create new agent (default enabled)
                    agent = AgentMetadata(
                        agent_name=agent_name,
                        display_name=display_name,
                        description=description,
                        is_public=True,  # Default enabled
                        requires_admin=False,
                        is_system=is_system,
                        is_deleted=False,
                    )
                    agent.set_aliases(aliases)
                    session.add(agent)
                    logger.info(f"Registered new agent '{agent_name}' in database")
                    action = "created"

                session.commit()

        return {
            "success": True,
            "agent": agent_name,
            "action": action
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"})


@router.get("/{agent_name}")
async def get_agent_details(agent_name: str) -> dict[str, Any]:
    """Get detailed information about a specific agent."""
    try:
        # Get authorized users and groups from database
        authorized_user_ids = []
        authorized_group_names = []

        with get_db_session() as session:
            # Get direct user permissions
            user_perms = session.query(AgentPermission).filter(
                AgentPermission.agent_name == agent_name
            ).all()
            authorized_user_ids = [p.slack_user_id for p in user_perms]

            # Get group permissions
            group_perms = session.query(AgentGroupPermission).filter(
                AgentGroupPermission.agent_name == agent_name
            ).all()
            authorized_group_names = [p.group_name for p in group_perms]

            # Get agent metadata for enabled state and system status
            metadata = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == agent_name
            ).first()
            is_enabled = metadata.is_public if metadata else False  # Default to disabled
            is_system = metadata.is_system if metadata else False

        details = {
            "name": agent_name,
            "authorized_user_ids": authorized_user_ids,
            "authorized_group_names": authorized_group_names,
            "is_public": is_enabled,
            "is_system": is_system,
        }

        return details
    except Exception as e:
        logger.error(f"Error getting agent details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.delete("/{agent_name}")
async def delete_agent(agent_name: str, admin_check: None = Depends(require_admin)) -> dict[str, Any]:
    """Soft delete an agent (mark as deleted, don't remove from database).

    System agents cannot be deleted.
    Deleted agents are hidden from list_agents() by default.

    Permission Handling:
    - Related permissions in agent_permissions and agent_group_permissions are PRESERVED
    - Permissions remain in the database but are effectively inactive (agent won't appear in lists)
    - If the agent is reactivated via register_agent(), existing permissions are automatically restored
    - This allows temporary removal without losing access control configuration
    - To permanently remove an agent and its permissions, manual database cleanup is required
    """
    try:
        with get_db_session() as session:
            agent_metadata = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == agent_name
            ).first()

            if not agent_metadata:
                raise HTTPException(
                    status_code=404,
                    detail=f"Agent '{agent_name}' not found"
                )

            # Prevent deleting system agents
            if agent_metadata.is_system:
                raise HTTPException(
                    status_code=403,
                    detail="Cannot delete system agents"
                )

            # Soft delete: mark as deleted
            agent_metadata.is_deleted = True
            agent_metadata.is_public = False  # Also disable when deleting
            session.commit()

            logger.info(f"Soft deleted agent '{agent_name}'")

            # Audit log
            log_agent_action(
                AuditAction.AGENT_DELETE,
                agent_name,
                {"display_name": agent_metadata.display_name}
            )

            return {
                "success": True,
                "data": {"agent_name": agent_name},
                "message": f"Agent '{agent_name}' marked as deleted"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"})


@router.get("/{agent_name}/usage")
async def get_agent_usage(agent_name: str) -> dict[str, Any]:
    """Get usage statistics for a specific agent from agent-service."""
    try:
        import httpx

        agent_service_url = os.getenv("AGENT_SERVICE_URL", "http://agent_service:8000")

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{agent_service_url}/api/metrics", timeout=5)

        if response.status_code != 200:
            raise HTTPException(status_code=503, detail={"error": "Unable to fetch usage stats"})

        data = response.json()
        agent_invocations = data.get("agent_invocations", {})
        by_agent = agent_invocations.get("by_agent", {})

        # Get stats for this specific agent
        total = by_agent.get(agent_name, 0)

        return {
            "agent_name": agent_name,
            "total_invocations": total,
            "all_time_stats": agent_invocations,  # Include overall stats for context
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent usage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/{agent_name}/toggle")
async def toggle_agent(agent_name: str, admin_check: None = Depends(require_admin)) -> dict[str, Any]:
    """Toggle agent enabled/disabled state."""
    try:
        with get_db_session() as session:
            # Get or create agent metadata
            agent_metadata = session.query(AgentMetadata).filter(
                AgentMetadata.agent_name == agent_name
            ).first()

            if not agent_metadata:
                # Create new metadata entry, default to enabled (is_public=True)
                agent_metadata = AgentMetadata(
                    agent_name=agent_name,
                    is_public=False,  # Toggle will make it True
                )
                session.add(agent_metadata)

            # Prevent disabling system agents
            if agent_metadata.is_system and agent_metadata.is_public:
                raise HTTPException(
                    status_code=403,
                    detail="Cannot disable system agents"
                )

            # Toggle the state
            agent_metadata.is_public = not agent_metadata.is_public
            session.commit()

            return {
                "agent_name": agent_name,
                "is_enabled": agent_metadata.is_public,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"})
