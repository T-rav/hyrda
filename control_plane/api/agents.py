"""Agent management endpoints."""

import logging
import os
import sys
from typing import Any

# Add shared directory to path
sys.path.insert(0, str(__file__).rsplit("/", 4)[0])

from fastapi import APIRouter, Depends, HTTPException, Request
from dependencies.service_auth import verify_service_auth
from models import (
    AgentGroupPermission,
    AgentMetadata,
    AgentPermission,
    ServiceAccount,
    get_db_session,
)
from shared.utils.error_responses import (
    ErrorCode,
    internal_error,
    not_found_error,
    validation_error,
)
from sqlalchemy import func
from utils.audit import AuditAction, log_agent_action
from utils.idempotency import require_idempotency
from utils.pagination import (
    build_pagination_response,
    get_pagination_params,
    paginate_query,
)
from utils.permissions import require_admin
from utils.validation import validate_agent_name, validate_display_name

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/agents",
    tags=["agents"],
)


@router.get("")
async def list_agents(request: Request) -> dict[str, Any]:
    """List all registered agents from database.

    Agents are now stored in the database (agent_metadata table) and can be
    configured dynamically without code changes. Bot and agent-service query
    this endpoint to discover available agents.

    Authentication: Allows both user and service-to-service auth (public endpoint for agent discovery)

    Query params:
        include_deleted: If "true", include soft-deleted agents (default: false)
        page: Page number (1-indexed, default: 1)
        per_page: Items per page (default: 50, max: 100)
    """
    try:
        include_deleted = (
            request.query_params.get("include_deleted", "false").lower() == "true"
        )

        page, per_page = get_pagination_params(
            request, default_per_page=50, max_per_page=100
        )

        with get_db_session() as session:
            query = session.query(AgentMetadata).order_by(AgentMetadata.agent_name)
            if not include_deleted:
                query = query.filter(~AgentMetadata.is_deleted)

            agents, total_count = paginate_query(query, page, per_page)

            # Batch load group counts for all agents in ONE query using GROUP BY
            # This prevents N+1 query problem
            agent_names = [a.agent_name for a in agents]
            group_counts_query = (
                session.query(
                    AgentGroupPermission.agent_name, func.count(AgentGroupPermission.id)
                )
                .filter(AgentGroupPermission.agent_name.in_(agent_names))
                .group_by(AgentGroupPermission.agent_name)
                .all()
            )

            group_counts = dict(group_counts_query)

            # Count service accounts that can access each agent
            # Service accounts with allowed_agents=NULL can access all agents
            # Service accounts with allowed_agents=JSON array can only access specific agents
            service_accounts = (
                session.query(ServiceAccount)
                .filter(ServiceAccount.is_active, ~ServiceAccount.is_revoked)
                .all()
            )

            import json

            service_account_counts = {}
            for agent_name in agent_names:
                count = 0
                for sa in service_accounts:
                    if sa.allowed_agents is None:
                        # Can access all agents
                        count += 1
                    else:
                        try:
                            allowed = json.loads(sa.allowed_agents)
                            if isinstance(allowed, list) and agent_name in allowed:
                                count += 1
                        except (json.JSONDecodeError, TypeError):
                            pass
                service_account_counts[agent_name] = count

            agents_data = []
            for agent in agents:
                group_count = group_counts.get(agent.agent_name, 0)
                service_account_count = service_account_counts.get(agent.agent_name, 0)

                agents_data.append(
                    {
                        "name": agent.agent_name,
                        "display_name": agent.display_name,
                        "aliases": agent.get_aliases(),
                        "description": agent.description or "No description",
                        "endpoint_url": agent.endpoint_url,
                        "langgraph_assistant_id": agent.langgraph_assistant_id,
                        "langgraph_url": agent.langgraph_url,
                        "is_enabled": agent.is_enabled,
                        "is_slack_visible": agent.is_slack_visible,
                        "requires_admin": agent.requires_admin,
                        "is_system": agent.is_system,
                        "is_deleted": agent.is_deleted,
                        "authorized_groups": group_count,
                        "authorized_service_accounts": service_account_count,
                    }
                )

            response = build_pagination_response(
                agents_data, total_count, page, per_page
            )
            return {"agents": response["items"], "pagination": response["pagination"]}

    except Exception as e:
        logger.error(f"Error listing agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=internal_error(str(e)))


async def _verify_service_only(request: Request) -> str:
    """Wrapper for verify_service_auth without allowed_services parameter."""
    return await verify_service_auth(request, allowed_services=None)


@router.post("/register")
@require_idempotency(ttl_hours=24)
async def register_agent(
    request: Request, service: str = Depends(_verify_service_only)
) -> dict[str, Any]:
    """Register or update an agent in the database.

    Called by agent-service on startup to sync available agents.
    Upserts agent metadata - creates if doesn't exist, updates if it does.

    This endpoint uses service-to-service authentication (service token in Authorization header).

    Headers:
        Authorization: Bearer <service_token>
        Idempotency-Key: Optional unique key to prevent duplicate registrations
    """
    try:
        data = await request.json()
        agent_name = data.get("name")
        display_name = data.get("display_name", agent_name)
        description = data.get("description", "")
        aliases = data.get("aliases", [])
        is_system = data.get("is_system", False)
        endpoint_url = data.get("endpoint_url")  # HTTP endpoint for invocation

        is_valid, error_msg = validate_agent_name(agent_name)
        if not is_valid:
            raise HTTPException(
                status_code=400, detail=validation_error(error_msg, field="name")
            )

        is_valid, error_msg = validate_display_name(display_name)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=validation_error(error_msg, field="display_name"),
            )

        with get_db_session() as session:
            with session.begin():
                agent = (
                    session.query(AgentMetadata)
                    .filter(AgentMetadata.agent_name == agent_name)
                    .with_for_update()
                    .first()
                )

                if agent and agent.is_deleted:
                    existing_active = (
                        session.query(AgentMetadata)
                        .filter(
                            AgentMetadata.agent_name == agent_name,
                            not AgentMetadata.is_deleted,
                        )
                        .first()
                    )
                    if existing_active:
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "error": f"Agent '{agent_name}' already exists",
                                "error_code": "AGENT_EXISTS",
                            },
                        )

                if agent and not agent.is_deleted:
                    agent.display_name = display_name
                    agent.description = description
                    if not agent.aliases_customized:
                        agent.set_aliases(aliases)
                        logger.info(
                            f"Updated agent '{agent_name}' aliases from agent registration"
                        )
                    else:
                        logger.info(
                            f"Preserved customized aliases for agent '{agent_name}'"
                        )
                    agent.is_system = is_system
                    agent.endpoint_url = endpoint_url
                    logger.info(f"Updated agent '{agent_name}' in database")
                    action = "updated"
                elif agent and agent.is_deleted:
                    agent.is_deleted = False
                    agent.is_enabled = True
                    agent.is_slack_visible = True
                    agent.display_name = display_name
                    agent.description = description
                    agent.set_aliases(aliases)
                    agent.aliases_customized = False
                    agent.is_system = is_system
                    agent.endpoint_url = endpoint_url
                    logger.info(f"Reactivated deleted agent '{agent_name}'")
                    action = "reactivated"
                else:
                    agent = AgentMetadata(
                        agent_name=agent_name,
                        display_name=display_name,
                        description=description,
                        endpoint_url=endpoint_url,
                        is_enabled=True,  # Default enabled
                        is_slack_visible=True,  # Default visible in Slack
                        requires_admin=False,
                        is_system=is_system,
                        is_deleted=False,
                    )
                    agent.set_aliases(aliases)
                    session.add(agent)
                    logger.info(f"Registered new agent '{agent_name}' in database")
                    action = "created"

                session.commit()

        return {"success": True, "agent": agent_name, "action": action}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"}
        )


@router.get("/{agent_name}")
async def get_agent_details(agent_name: str) -> dict[str, Any]:
    """Get detailed information about a specific agent."""
    try:
        authorized_user_ids = []
        authorized_group_names = []

        with get_db_session() as session:
            user_perms = (
                session.query(AgentPermission)
                .filter(AgentPermission.agent_name == agent_name)
                .all()
            )
            authorized_user_ids = [p.slack_user_id for p in user_perms]

            group_perms = (
                session.query(AgentGroupPermission)
                .filter(AgentGroupPermission.agent_name == agent_name)
                .all()
            )
            authorized_group_names = [p.group_name for p in group_perms]

            metadata = (
                session.query(AgentMetadata)
                .filter(AgentMetadata.agent_name == agent_name)
                .first()
            )
            is_enabled = metadata.is_enabled if metadata else False
            is_slack_visible = metadata.is_slack_visible if metadata else False
            is_system = metadata.is_system if metadata else False

        details = {
            "name": agent_name,
            "authorized_user_ids": authorized_user_ids,
            "authorized_group_names": authorized_group_names,
            "is_enabled": is_enabled,
            "is_slack_visible": is_slack_visible,
            "is_system": is_system,
        }

        return details
    except Exception as e:
        logger.error(f"Error getting agent details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.delete("/{agent_name}")
async def delete_agent(
    agent_name: str, admin_check: None = Depends(require_admin)
) -> dict[str, Any]:
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
            agent_metadata = (
                session.query(AgentMetadata)
                .filter(AgentMetadata.agent_name == agent_name)
                .first()
            )

            if not agent_metadata:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Agent", agent_name)
                )

            # Prevent deleting system agents
            if agent_metadata.is_system:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "Cannot delete system agents",
                        "error_code": ErrorCode.FORBIDDEN,
                    },
                )

            # Soft delete: mark as deleted and disable
            agent_metadata.is_deleted = True
            agent_metadata.is_enabled = False  # Disable when deleting
            agent_metadata.is_slack_visible = False  # Hide from Slack when deleting
            session.commit()

            logger.info(f"Soft deleted agent '{agent_name}'")

            log_agent_action(
                AuditAction.AGENT_DELETE,
                agent_name,
                {"display_name": agent_metadata.display_name},
            )

            return {
                "success": True,
                "data": {"agent_name": agent_name},
                "message": f"Agent '{agent_name}' marked as deleted",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"}
        )


@router.get("/{agent_name}/usage")
async def get_agent_usage(agent_name: str) -> dict[str, Any]:
    """Get usage statistics for a specific agent from agent-service."""
    try:
        import httpx

        agent_service_url = os.getenv("AGENT_SERVICE_URL", "http://agent_service:8000")

        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(f"{agent_service_url}/api/metrics", timeout=5)

        if response.status_code != 200:
            raise HTTPException(
                status_code=503, detail={"error": "Unable to fetch usage stats"}
            )

        data = response.json()
        agent_invocations = data.get("agent_invocations", {})
        by_agent = agent_invocations.get("by_agent", {})

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
async def toggle_agent_enabled(
    agent_name: str, admin_check: None = Depends(require_admin)
) -> dict[str, Any]:
    """Toggle agent enabled/disabled state.

    System agents cannot be disabled.
    When disabled, agent is unavailable everywhere (takes priority over Slack visibility).
    """
    try:
        with get_db_session() as session:
            agent_metadata = (
                session.query(AgentMetadata)
                .filter(AgentMetadata.agent_name == agent_name)
                .first()
            )

            if not agent_metadata:
                # Create new metadata entry
                agent_metadata = AgentMetadata(
                    agent_name=agent_name,
                    is_enabled=False,  # Toggle will make it True
                    is_slack_visible=True,
                )
                session.add(agent_metadata)

            if agent_metadata.is_system and agent_metadata.is_enabled:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "Cannot disable system agents",
                        "error_code": ErrorCode.FORBIDDEN,
                    },
                )

            agent_metadata.is_enabled = not agent_metadata.is_enabled
            session.commit()

            return {
                "agent_name": agent_name,
                "is_enabled": agent_metadata.is_enabled,
                "is_slack_visible": agent_metadata.is_slack_visible,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling agent enabled state: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"}
        )


@router.post("/{agent_name}/toggle-slack")
async def toggle_agent_slack_visibility(
    agent_name: str, admin_check: None = Depends(require_admin)
) -> dict[str, Any]:
    """Toggle agent Slack visibility.

    Controls whether agent appears in Slack command routing.
    Agent must be enabled for this to take effect.
    """
    try:
        with get_db_session() as session:
            agent_metadata = (
                session.query(AgentMetadata)
                .filter(AgentMetadata.agent_name == agent_name)
                .first()
            )

            if not agent_metadata:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Agent", agent_name)
                )

            agent_metadata.is_slack_visible = not agent_metadata.is_slack_visible
            session.commit()

            return {
                "agent_name": agent_name,
                "is_enabled": agent_metadata.is_enabled,
                "is_slack_visible": agent_metadata.is_slack_visible,
                "effective_in_slack": agent_metadata.is_visible_in_slack(),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling agent Slack visibility: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"}
        )


@router.put("/{agent_name}/aliases")
async def update_agent_aliases(
    agent_name: str, request: Request, admin_check: None = Depends(require_admin)
) -> dict[str, Any]:
    """Update agent aliases (admin-only, preserves overrides on agent re-registration).

    Request body:
        {"aliases": ["alias1", "alias2", "alias3"]}

    This sets aliases_customized=True, preventing future agent registrations
    from overwriting these admin-edited aliases.
    """
    try:
        data = await request.json()
        aliases = data.get("aliases", [])

        if not isinstance(aliases, list):
            raise HTTPException(
                status_code=400,
                detail=validation_error("aliases must be a list", field="aliases"),
            )

        import re

        for alias in aliases:
            if not isinstance(alias, str) or not re.match(r"^[\w\s-]+$", alias):
                raise HTTPException(
                    status_code=400,
                    detail=validation_error(
                        f"Invalid alias '{alias}' - must contain only letters, numbers, spaces, hyphens, underscores",
                        field="aliases",
                    ),
                )

        with get_db_session() as session:
            agent_metadata = (
                session.query(AgentMetadata)
                .filter(AgentMetadata.agent_name == agent_name)
                .first()
            )

            if not agent_metadata:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Agent", agent_name)
                )

            agent_metadata.set_aliases(aliases)
            agent_metadata.aliases_customized = True
            session.commit()

            logger.info(f"Admin updated aliases for agent '{agent_name}': {aliases}")

            log_agent_action(
                AuditAction.AGENT_UPDATE,
                agent_name,
                {"aliases": aliases, "aliases_customized": True},
            )

            return {
                "success": True,
                "agent_name": agent_name,
                "aliases": aliases,
                "aliases_customized": True,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent aliases: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"}
        )


@router.get("/{agent_name}/alias-conflicts")
async def check_alias_conflicts(agent_name: str) -> dict[str, Any]:
    """Check if agent's aliases conflict with other agents.

    Returns list of conflicts where this agent's aliases are used by other agents.
    Helps admins detect and resolve alias conflicts.
    """
    try:
        with get_db_session() as session:
            agent = (
                session.query(AgentMetadata)
                .filter(
                    AgentMetadata.agent_name == agent_name,
                    ~AgentMetadata.is_deleted,
                )
                .first()
            )

            if not agent:
                raise HTTPException(
                    status_code=404, detail=not_found_error("Agent", agent_name)
                )

            this_agent_aliases = set(agent.get_aliases())
            if not this_agent_aliases:
                return {
                    "agent_name": agent_name,
                    "aliases": [],
                    "conflicts": [],
                }

            # Get all other active agents
            other_agents = (
                session.query(AgentMetadata)
                .filter(
                    AgentMetadata.agent_name != agent_name,
                    ~AgentMetadata.is_deleted,
                )
                .all()
            )

            conflicts = []
            for other_agent in other_agents:
                other_aliases = set(other_agent.get_aliases())

                # Check for overlapping aliases
                overlapping = this_agent_aliases & other_aliases
                if overlapping:
                    conflicts.append(
                        {
                            "conflicting_agent": other_agent.agent_name,
                            "conflicting_aliases": list(overlapping),
                            "is_enabled": other_agent.is_enabled,
                            "is_slack_visible": other_agent.is_slack_visible,
                        }
                    )

                # Check if this agent's aliases conflict with other agent's primary name
                if other_agent.agent_name in this_agent_aliases:
                    conflicts.append(
                        {
                            "conflicting_agent": other_agent.agent_name,
                            "conflicting_aliases": [other_agent.agent_name],
                            "conflict_type": "primary_name",
                            "is_enabled": other_agent.is_enabled,
                            "is_slack_visible": other_agent.is_slack_visible,
                        }
                    )

            return {
                "agent_name": agent_name,
                "aliases": list(this_agent_aliases),
                "conflicts": conflicts,
                "has_conflicts": len(conflicts) > 0,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking alias conflicts: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"}
        )
