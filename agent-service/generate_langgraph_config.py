#!/usr/bin/env python3
"""Generate langgraph.json by merging configs from system and custom agents.

Merges:
- agent-service/agents/langgraph.json (system agents - always present)
- custom_agents/langgraph.json (custom agents - optional, mounted externally)

Output: agent-service/langgraph.json
"""

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_json_config(path: Path) -> dict:
    """Load JSON config file if it exists."""
    if not path.exists():
        logger.warning(f"Config not found: {path}")
        return {}

    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.error(f"Failed to load {path}: {e}")
        return {}


def merge_langgraph_configs(system_config: dict, custom_config: dict) -> dict:
    """Merge system and custom agent configs.

    Args:
        system_config: Config from agent-service/agents/langgraph.json
        custom_config: Config from custom_agents/langgraph.json

    Returns:
        Merged config with all agents
    """
    merged = {"dependencies": [".", "../"], "graphs": {}, "env": "../.env"}

    # Merge graphs from both configs
    if "graphs" in system_config:
        merged["graphs"].update(system_config["graphs"])
        logger.info(f"Loaded {len(system_config['graphs'])} system agents")

    if "graphs" in custom_config:
        merged["graphs"].update(custom_config["graphs"])
        logger.info(f"Loaded {len(custom_config['graphs'])} custom agents")

    # Add custom_agents to dependencies if custom agents exist
    if custom_config.get("graphs"):
        merged["dependencies"].append("../custom_agents")

    return merged


def generate_langgraph_config(output_path: Path):
    """Generate unified langgraph.json from system and custom configs."""

    # Paths
    agent_service_dir = Path(__file__).parent
    system_config_path = agent_service_dir / "agents" / "langgraph.json"
    custom_config_path = agent_service_dir.parent / "custom_agents" / "langgraph.json"

    logger.info("Merging LangGraph configs...")
    logger.info(f"System config: {system_config_path}")
    logger.info(f"Custom config: {custom_config_path}")

    # Load configs
    system_config = load_json_config(system_config_path)
    custom_config = load_json_config(custom_config_path)

    # Merge
    merged_config = merge_langgraph_configs(system_config, custom_config)

    if not merged_config["graphs"]:
        logger.error("No agents found in any config!")
        sys.exit(1)

    # Write merged config
    output_path.write_text(json.dumps(merged_config, indent=2) + "\n")

    logger.info(f"Generated {output_path}")
    logger.info(f"Total agents: {len(merged_config['graphs'])}")
    for name in sorted(merged_config["graphs"].keys()):
        logger.info(f"  - {name}")


if __name__ == "__main__":
    output_path = Path(__file__).parent / "langgraph.json"
    generate_langgraph_config(output_path)
