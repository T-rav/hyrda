"""Node for listing available agents filtered by user permissions."""

import logging
import os
from typing import Any

import urllib3

from ..state import AgentInfo, HelpAgentState

logger = logging.getLogger(__name__)

# Suppress SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _fetch_control_plane_agents() -> list[dict[str, Any]]:
    """Fetch all agents from control plane API.

    Returns:
        List of agent data dicts from control plane
    """
    try:
        import requests

        control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control_plane:6001")

        response = requests.get(
            f"{control_plane_url}/api/agents",
            timeout=5,
            verify=False,  # nosec B501 - Internal Docker network  # nosemgrep: python.requests.security.disabled-cert-validation.disabled-cert-validation, python.lang.security.audit.insecure-transport.requests.request-with-http.request-with-http
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("agents", [])
        else:
            logger.warning(f"Control plane returned status {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"Error fetching agents from control plane: {e}")
        return []


def _fetch_user_groups(user_id: str) -> list[str]:
    """Fetch groups that a user belongs to.

    Args:
        user_id: Slack user ID

    Returns:
        List of group names the user belongs to
    """
    try:
        import requests

        control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control_plane:6001")

        # Fetch all groups and check user membership
        # This is a simplified approach - in production, you'd want a dedicated endpoint
        response = requests.get(
            f"{control_plane_url}/api/groups",
            timeout=5,
            verify=False,  # nosec B501 - Internal Docker network  # nosemgrep: python.requests.security.disabled-cert-validation.disabled-cert-validation, python.lang.security.audit.insecure-transport.requests.request-with-http.request-with-http
        )

        if response.status_code == 200:
            data = response.json()
            groups = data.get("groups", [])
            user_groups = []

            for group in groups:
                group_name = group.get("group_name")
                # Check if user is in this group
                users_response = requests.get(
                    f"{control_plane_url}/api/groups/{group_name}/users",
                    timeout=5,
                    verify=False,  # nosec B501  # nosemgrep: python.requests.security.disabled-cert-validation.disabled-cert-validation, python.lang.security.audit.insecure-transport.requests.request-with-http.request-with-http
                )
                if users_response.status_code == 200:
                    users_data = users_response.json()
                    users = users_data.get("users", [])
                    if any(u.get("user_id") == user_id for u in users):
                        user_groups.append(group_name)

            return user_groups
        else:
            logger.warning(f"Control plane returned status {response.status_code}")
            return ["all_users"]  # Default to all_users if API fails

    except Exception as e:
        logger.error(f"Error fetching user groups: {e}")
        return ["all_users"]  # Default to all_users if API fails


def _fetch_agent_permissions(agent_name: str) -> list[str]:
    """Fetch groups that have access to a specific agent.

    Args:
        agent_name: Name of the agent

    Returns:
        List of group names with access to this agent
    """
    try:
        import requests

        control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control_plane:6001")

        response = requests.get(
            f"{control_plane_url}/api/agents/{agent_name}",
            timeout=5,
            verify=False,  # nosec B501 - Internal Docker network  # nosemgrep: python.requests.security.disabled-cert-validation.disabled-cert-validation, python.lang.security.audit.insecure-transport.requests.request-with-http.request-with-http
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("authorized_group_names", [])
        else:
            logger.warning(f"Control plane returned status {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"Error fetching agent permissions: {e}")
        return []


def _filter_agents_by_permission(
    agents: list[AgentInfo], user_groups: list[str]
) -> list[AgentInfo]:
    """Filter agents based on user group permissions.

    Args:
        agents: All available agents
        user_groups: Groups the user belongs to

    Returns:
        Agents the user has access to
    """
    accessible = []

    for agent in agents:
        # System agents are always accessible
        if agent.is_system:
            accessible.append(agent)
            continue

        # Check if agent is enabled
        if not agent.is_enabled:
            continue

        # Check if user has permission via groups
        try:
            authorized_groups = _fetch_agent_permissions(agent.name)

            # If no specific permissions set, agent is accessible to all
            if not authorized_groups:
                accessible.append(agent)
                continue

            # Check if user's groups intersect with authorized groups
            if any(group in authorized_groups for group in user_groups):
                accessible.append(agent)

        except Exception as e:
            logger.warning(f"Error checking permissions for {agent.name}: {e}")
            # Default to accessible on error for better UX
            accessible.append(agent)

    return accessible


def list_agents_node(state: HelpAgentState) -> dict[str, Any]:
    """List available agents filtered by user permissions.

    This node:
    1. Fetches all agents from control plane
    2. Determines user's groups
    3. Filters agents based on permissions
    4. Formats the response

    Args:
        state: Current workflow state

    Returns:
        Updated state with response
    """
    user_id = state.get("user_id", "")

    logger.info(f"HelpAgent listing available agents for user: {user_id}")

    # Fetch user's groups
    user_groups = _fetch_user_groups(user_id)
    logger.info(f"User {user_id} is in groups: {user_groups}")

    # Fetch all agents from control plane
    raw_agents = _fetch_control_plane_agents()

    # Convert to AgentInfo objects
    all_agents = []
    for agent_data in raw_agents:
        if agent_data.get("is_deleted"):
            continue

        agent = AgentInfo(
            name=agent_data.get("name", ""),
            display_name=agent_data.get("display_name", agent_data.get("name", "")),
            description=agent_data.get("description", "No description available"),
            aliases=agent_data.get("aliases", []),
            is_enabled=agent_data.get("is_enabled", True),
            is_system=agent_data.get("is_system", False),
        )
        all_agents.append(agent)

    # Filter agents by user permissions
    accessible_agents = _filter_agents_by_permission(all_agents, user_groups)

    # Sort by name
    accessible_agents.sort(key=lambda a: a.name)

    logger.info(f"Found {len(accessible_agents)} accessible agents for user {user_id}")

    # Build response
    response_lines = [
        "🤖 **Available Bot Agents**\n",
        "Use these commands to interact with specialized agents:\n",
    ]

    if not accessible_agents:
        response_lines.append(
            "\n_No agents available. Contact an administrator for access._"
        )
    else:
        for agent in accessible_agents:
            agent_line = f"\n**{agent.name}** or **-{agent.name}**"
            if agent.aliases:
                alias_text = ", ".join(
                    [f"{alias} or -{alias}" for alias in agent.aliases]
                )
                agent_line += f" (aliases: {alias_text})"

            response_lines.append(agent_line)
            response_lines.append(f"  {agent.description}")

    response_lines.append(
        "\n\n**Usage:** Type `-<command> <your query>` or `<command> <your query>` to use an agent"
    )
    response_lines.append("**Examples:**")
    response_lines.append("  • `-profile AllCampus AI` or `profile AllCampus AI`")
    response_lines.append(
        "  • `-meddic analyze this deal` or `meddic analyze this deal`"
    )

    response = "\n".join(response_lines)

    return {
        "response": response,
        "accessible_agents": accessible_agents,
        "metadata": {
            "agent": "help",
            "agent_count": len(accessible_agents),
            "user_groups": user_groups,
        },
    }
