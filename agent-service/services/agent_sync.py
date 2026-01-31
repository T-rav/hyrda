"""Agent synchronization with control plane.

On startup, agent-service dynamically discovers all available agents and
registers them with control plane. This allows control plane UI to enable/disable
agents dynamically without code changes.
"""

import json
import logging
import os
from pathlib import Path

import urllib3

# Suppress SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def _discover_agents_from_langgraph() -> list[dict]:
    """Discover agents from merged langgraph.json.

    Supports two formats:
    1. Simple: "agent_name": "module.path:function"
    2. Extended: "agent_name": {"graph": "module.path:function", "metadata": {...}}

    Returns:
        List of agent metadata dicts with name, display_name, aliases, description, is_system
    """
    langgraph_path = Path(__file__).parent.parent / "langgraph.json"

    if not langgraph_path.exists():
        logger.warning(f"langgraph.json not found at {langgraph_path}")
        return []

    try:
        with open(langgraph_path) as f:
            config = json.load(f)

        graphs = config.get("graphs", {})
        agents = []

        for agent_name, agent_config in graphs.items():
            # Parse agent config (supports both string and dict formats)
            if isinstance(agent_config, str):
                # Simple format: "agent_name": "module:function"
                metadata = {}
            elif isinstance(agent_config, dict):
                # Extended format: "agent_name": {"graph": "...", "metadata": {...}}
                metadata = agent_config.get("metadata", {})
            else:
                logger.warning(
                    f"Invalid config format for agent '{agent_name}', skipping"
                )
                continue

            # Build agent data with defaults
            agent_data = {
                "name": agent_name,
                "display_name": metadata.get(
                    "display_name", agent_name.replace("_", " ").title()
                ),
                "description": metadata.get("description", f"Agent for {agent_name}"),
                "aliases": metadata.get("aliases", []),
                "is_system": False,  # Default: can be disabled by admins
            }

            # Special case: "help" is always a system agent
            if agent_name == "help":
                agent_data["is_system"] = True
                # Use metadata if provided, otherwise use defaults
                if not metadata.get("display_name"):
                    agent_data["display_name"] = "Help Agent"
                if not metadata.get("description"):
                    agent_data["description"] = (
                        "List available bot agents and their aliases"
                    )
                if not metadata.get("aliases"):
                    agent_data["aliases"] = ["help", "agents"]

            agents.append(agent_data)

        logger.info(
            f"Discovered {len(agents)} agents from langgraph.json: {[a['name'] for a in agents]}"
        )
        return agents

    except Exception as e:
        logger.error(f"Error reading langgraph.json: {e}", exc_info=True)
        return []


def sync_agents_to_control_plane() -> None:
    """Register all available agents with control plane on startup.

    Dynamically discovers agents from langgraph.json and registers them with
    control plane. This allows:
    - Control plane UI to show all available agents
    - Enable/disable agents via UI
    - Dynamic agent discovery without code changes
    - New agents auto-register on deployment
    """
    try:
        import requests

        # Agent service hostname for internal Docker network
        agent_service_host = os.getenv("AGENT_SERVICE_HOST", "agent_service")

        # Discover agents dynamically from langgraph.json
        discovered_agents = _discover_agents_from_langgraph()

        if not discovered_agents:
            logger.warning("No agents discovered - skipping registration")
            return

        # Build registration payloads with endpoint URLs
        agents_to_register = []
        for agent_data in discovered_agents:
            agent_data["endpoint_url"] = (
                f"http://{agent_service_host}:8000/api/agents/{agent_data['name']}/invoke"
            )
            agents_to_register.append(agent_data)

        control_plane_url = os.getenv("CONTROL_PLANE_URL", "http://control_plane:6001")

        # Get service token for authentication
        service_token = os.getenv("BOT_SERVICE_TOKEN", "")
        if not service_token:
            logger.warning(
                "No BOT_SERVICE_TOKEN configured - agent registration will fail"
            )

        for agent_data in agents_to_register:
            try:
                headers = {}
                if service_token:
                    headers["Authorization"] = f"Bearer {service_token}"

                response = requests.post(
                    f"{control_plane_url}/api/agents/register",
                    json=agent_data,
                    headers=headers,
                    timeout=5,
                    verify=False,  # nosec B501 - Internal Docker network with self-signed certs
                )
                if response.status_code == 200:
                    logger.info(
                        f"✓ Registered agent '{agent_data['name']}' with control plane"
                    )
                else:
                    logger.warning(
                        f"Failed to register agent '{agent_data['name']}': HTTP {response.status_code}"
                    )
            except Exception as e:
                logger.warning(f"Failed to register agent '{agent_data['name']}': {e}")

        logger.info(
            f"Agent sync complete - registered {len(agents_to_register)} agents"
        )

    except Exception as e:
        logger.error(f"Error syncing agents to control plane: {e}")
        # Don't fail startup if sync fails - agents can still work
