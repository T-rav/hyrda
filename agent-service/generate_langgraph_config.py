#!/usr/bin/env python3
"""Generate langgraph.json by merging configs from system and custom agents.

Merges:
- agent-service/agents/langgraph.json (system agents - always present)
- custom_agents/langgraph.json (custom agents - optional, mounted externally)

Output: agent-service/langgraph.json (simple format for langgraph dev compatibility)
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


def extract_graph_spec(spec):
    """Extract graph module:function string from spec.

    Handles both simple format (string) and extended format (dict with 'graph' key).
    """
    if isinstance(spec, str):
        return spec
    elif isinstance(spec, dict) and "graph" in spec:
        return spec["graph"]
    else:
        logger.warning(f"Invalid spec format: {spec}")
        return None


def generate_langgraph_config(output_path: Path):
    """Generate unified langgraph.json from system and custom configs.

    Always outputs simple format: {"agent_name": "module:function"}
    This ensures compatibility with both production and langgraph dev mode.
    """

    # Paths
    agent_service_dir = Path(__file__).parent
    system_config_path = agent_service_dir / "agents" / "langgraph.json"
    custom_config_path = agent_service_dir / "custom_agents" / "langgraph.json"

    logger.info("Merging LangGraph configs...")
    logger.info(f"System config: {system_config_path}")
    logger.info(f"Custom config: {custom_config_path}")

    # Load configs
    system_config = load_json_config(system_config_path)
    custom_config = load_json_config(custom_config_path)

    # Build simple config (always string format for dev compatibility)
    merged = {"dependencies": ["."], "graphs": {}, "env": "../.env"}

    # Add system agents
    for name, spec in system_config.get("graphs", {}).items():
        graph_spec = extract_graph_spec(spec)
        if graph_spec:
            merged["graphs"][name] = graph_spec

    logger.info(f"Loaded {len(merged['graphs'])} system agents")

    # Add custom agents
    for name, spec in custom_config.get("graphs", {}).items():
        graph_spec = extract_graph_spec(spec)
        if graph_spec:
            merged["graphs"][name] = graph_spec

    custom_count = len(merged["graphs"]) - len(system_config.get("graphs", {}))
    if custom_count > 0:
        logger.info(f"Loaded {custom_count} custom agents")
        # ./custom_agents is correct for both production and langgraph dev
        # langgraph.json is at /app/langgraph.json, custom_agents at /app/custom_agents
        merged["dependencies"].append("./custom_agents")

    if not merged["graphs"]:
        logger.error("No agents found in any config!")
        sys.exit(1)

    # Write merged config
    output_path.write_text(json.dumps(merged, indent=2) + "\n")

    logger.info(f"Generated {output_path}")
    logger.info(f"Total agents: {len(merged['graphs'])}")
    for name in sorted(merged["graphs"].keys()):
        logger.info(f"  - {name}")


if __name__ == "__main__":
    output_path = Path(__file__).parent / "langgraph.json"
    generate_langgraph_config(output_path)
