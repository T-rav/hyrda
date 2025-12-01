"""Audit logging for admin actions."""

import logging
from datetime import UTC, datetime
from typing import Any

from flask import request, session

logger = logging.getLogger(__name__)


def log_admin_action(
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
    success: bool = True,
) -> None:
    """Log an admin action for audit trail.

    Args:
        action: The action performed (e.g., "delete", "grant_permission", "revoke_permission")
        resource_type: Type of resource affected (e.g., "agent", "user", "group")
        resource_id: Identifier of the resource (e.g., agent name, user email, group name)
        details: Optional additional details about the action
        success: Whether the action succeeded (default: True)

    Example:
        >>> log_admin_action("delete", "agent", "profile", {"reason": "deprecated"})
        >>> log_admin_action("grant_permission", "agent_group", "engineering/profile")
    """
    user_email = session.get("user_email", "unknown")
    timestamp = datetime.now(UTC).isoformat()

    # Get request information
    ip_address = request.remote_addr if request else "unknown"
    user_agent = request.headers.get("User-Agent", "unknown") if request else "unknown"

    audit_entry = {
        "timestamp": timestamp,
        "user": user_email,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "success": success,
        "ip_address": ip_address,
        "user_agent": user_agent,
    }

    if details:
        audit_entry["details"] = details

    # Log as structured JSON for easy parsing
    if success:
        logger.info(f"AUDIT: {audit_entry}")
    else:
        logger.warning(f"AUDIT_FAILED: {audit_entry}")


def log_agent_action(action: str, agent_name: str, details: dict[str, Any] | None = None) -> None:
    """Log an agent-related action.

    Args:
        action: The action performed (e.g., "delete", "toggle", "register")
        agent_name: Name of the agent
        details: Optional additional details
    """
    log_admin_action(action, "agent", agent_name, details)


def log_permission_action(
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Log a permission-related action.

    Args:
        action: The action performed (e.g., "grant", "revoke")
        resource_type: Type of permission (e.g., "agent_permission", "agent_group_permission")
        resource_id: Identifier (e.g., "user@example.com/profile", "engineering/profile")
        details: Optional additional details
    """
    log_admin_action(action, resource_type, resource_id, details)


def log_user_action(action: str, user_email: str, details: dict[str, Any] | None = None) -> None:
    """Log a user management action.

    Args:
        action: The action performed (e.g., "set_admin", "add_to_group", "remove_from_group")
        user_email: Email of the user
        details: Optional additional details
    """
    log_admin_action(action, "user", user_email, details)


def log_group_action(action: str, group_name: str, details: dict[str, Any] | None = None) -> None:
    """Log a group management action.

    Args:
        action: The action performed (e.g., "create", "delete", "update")
        group_name: Name of the group
        details: Optional additional details
    """
    log_admin_action(action, "group", group_name, details)


# Audit action constants for consistency
class AuditAction:
    """Standard audit action names."""

    # Agent actions
    AGENT_DELETE = "delete_agent"
    AGENT_TOGGLE = "toggle_agent"
    AGENT_REGISTER = "register_agent"

    # Permission actions
    GRANT_PERMISSION = "grant_permission"
    REVOKE_PERMISSION = "revoke_permission"

    # User actions
    SET_ADMIN = "set_admin"
    ADD_TO_GROUP = "add_to_group"
    REMOVE_FROM_GROUP = "remove_from_group"

    # Group actions
    CREATE_GROUP = "create_group"
    DELETE_GROUP = "delete_group"
    UPDATE_GROUP = "update_group"
