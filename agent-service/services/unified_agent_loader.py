"""Unified agent loader - loads all agents from merged langgraph.json.

All agents (system + custom) are LangGraph graphs defined in langgraph.json.
The startup.sh script merges system + custom configs into /app/langgraph.json.
This loader imports and builds all graphs from that merged config.
"""

import importlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class UnifiedAgentLoader:
    """Loads all agents from merged langgraph.json."""

    def __init__(self, config_path: str = "/app/langgraph.json"):
        """Initialize agent loader.

        Args:
            config_path: Path to merged langgraph.json
        """
        self.config_path = Path(config_path)
        self._loaded_agents: dict[str, Any] = {}

    def discover_agents(self) -> dict[str, Any]:
        """Load all agents from langgraph.json.

        Returns:
            Dict mapping agent names to CompiledStateGraph instances
        """
        if self._loaded_agents:
            return self._loaded_agents

        if not self.config_path.exists():
            logger.error(f"langgraph.json not found: {self.config_path}")
            return {}

        try:
            config = json.loads(self.config_path.read_text())
        except Exception as e:
            logger.error(f"Failed to parse langgraph.json: {e}")
            return {}

        # Add dependencies to Python path
        for dep in config.get("dependencies", []):
            dep_path = self.config_path.parent / dep
            dep_str = str(dep_path.resolve())
            if dep_str not in sys.path:
                sys.path.insert(0, dep_str)

        # Load all graphs
        graphs = config.get("graphs", {})
        loaded = {}

        for agent_name, graph_spec in graphs.items():
            try:
                agent = self._load_graph(agent_name, graph_spec)
                if agent:
                    loaded[agent_name.lower()] = agent
                    logger.info(f"✅ Loaded agent: {agent_name}")
            except Exception as e:
                logger.error(f"❌ Failed to load {agent_name}: {e}", exc_info=True)

        self._loaded_agents = loaded
        logger.info(f"📦 Loaded {len(loaded)} agents from langgraph.json")
        return loaded

    def _load_graph(self, agent_name: str, graph_spec: str | dict) -> Any:
        """Load graph from module:function specification.

        Args:
            agent_name: Name of the agent
            graph_spec: "module:function" or {"graph": "module:function", ...}

        Returns:
            CompiledStateGraph instance
        """
        # Extract module:function string
        if isinstance(graph_spec, dict):
            spec_str = graph_spec.get("graph")
        else:
            spec_str = graph_spec

        if not spec_str or ":" not in str(spec_str):
            logger.error(f"Invalid spec for {agent_name}: {graph_spec}")
            return None

        module_path, function_name = spec_str.split(":", 1)

        # Import module and call builder
        try:
            module = importlib.import_module(module_path)
            builder = getattr(module, function_name, None)

            if not builder or not callable(builder):
                logger.error(f"Builder {function_name} not found in {module_path}")
                return None

            return builder()

        except Exception as e:
            logger.error(f"Failed to build {agent_name}: {e}", exc_info=True)
            return None


# Singleton
_loader: UnifiedAgentLoader | None = None


def get_unified_loader() -> UnifiedAgentLoader:
    """Get singleton loader instance."""
    global _loader
    if _loader is None:
        _loader = UnifiedAgentLoader()
    return _loader
