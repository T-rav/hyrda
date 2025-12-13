"""Agent synchronization with control plane.

On startup, agent-service registers its available agents with control plane.
This allows control plane UI to enable/disable agents dynamically.
"""

import logging
import os

logger = logging.getLogger(__name__)


def sync_agents_to_control_plane() -> None:
    """Register all available agents with control plane on startup.

    Sends agent metadata (name, aliases, description) to control plane
    which upserts them into the database. This allows:
    - Control plane UI to show all available agents
    - Enable/disable agents via UI
    - Dynamic agent discovery without code changes
    """
    try:
        import requests

        # Get local agent implementations

        agents_to_register = [
            {
                "name": "profile",
                "display_name": "Company Profile",
                "description": "Generate comprehensive company profiles through deep research (supports specific focus areas like 'AI needs', 'DevOps practices', etc.)",
                "aliases": ["-profile"],
                "is_system": False,
            },
            {
                "name": "meddic",
                "display_name": "MEDDIC Coach",
                "description": "MEDDPICC sales qualification and coaching - transforms sales notes into structured analysis with coaching insights",
                "aliases": ["medic", "meddpicc"],
                "is_system": False,
            },
            {
                "name": "help",
                "display_name": "Help Agent",
                "description": "List available bot agents and their aliases",
                "aliases": ["agents"],
                "is_system": True,  # System agents cannot be disabled
            },
        ]

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
