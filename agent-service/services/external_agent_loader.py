"""Dynamic external agent loader for client-provided agents.

Allows clients to mount their own agents directory and load agents at runtime
without rebuilding the Docker image. Supports hot-reload for development.

Client Usage:
    1. Mount agents directory in docker-compose.yml:
       volumes:
         - ./my_agents:/app/external_agents:ro

    2. Set environment variable:
       EXTERNAL_AGENTS_PATH=/app/external_agents

    3. Agent directory structure:
       /app/external_agents/
       ├── my_agent/
       │   ├── agent.py (must have Agent class)
       │   ├── tools.py (optional)
       │   └── requirements.txt (optional, client must pre-install)
       └── another_agent/
           └── agent.py
"""

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ExternalAgentLoader:
    """Loads agents from external directory (client-provided)."""

    def __init__(self, external_agents_path: str | None = None):
        """Initialize external agent loader.

        Args:
            external_agents_path: Path to external agents directory.
                                  Defaults to EXTERNAL_AGENTS_PATH env var.
        """
        self.external_path = external_agents_path or os.getenv("EXTERNAL_AGENTS_PATH")
        self._loaded_agents: dict[str, type] = {}
        self._agent_modules: dict[str, Any] = {}  # Track modules for reload

        if self.external_path:
            logger.info(f"External agent loader initialized: {self.external_path}")
        else:
            logger.info("No external agents path configured (EXTERNAL_AGENTS_PATH not set)")

    def discover_agents(self) -> dict[str, type]:
        """Discover and load all agents from external directory.

        Returns:
            Dict mapping agent names to agent classes
        """
        if not self.external_path:
            return {}

        external_dir = Path(self.external_path)
        if not external_dir.exists():
            logger.warning(f"External agents directory not found: {self.external_path}")
            return {}

        discovered = {}

        # Scan for agent directories
        for agent_dir in external_dir.iterdir():
            if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
                continue

            agent_file = agent_dir / "agent.py"
            if not agent_file.exists():
                logger.warning(f"Skipping {agent_dir.name}: No agent.py found")
                continue

            try:
                agent_class = self._load_agent_module(agent_dir.name, agent_file)
                if agent_class:
                    discovered[agent_dir.name] = agent_class
                    logger.info(f"✅ Loaded external agent: {agent_dir.name}")
            except Exception as e:
                logger.error(f"❌ Failed to load agent {agent_dir.name}: {e}", exc_info=True)

        self._loaded_agents = discovered
        return discovered

    def _load_agent_module(self, agent_name: str, agent_file: Path) -> type | None:
        """Load agent class from Python file.

        Args:
            agent_name: Name of the agent
            agent_file: Path to agent.py file

        Returns:
            Agent class if found, None otherwise
        """
        # Import as proper package: external_agents.agent_name.agent
        package_name = f"external_agents.{agent_name}"
        module_name = f"{package_name}.agent"

        try:
            # Add external_agents parent to sys.path (not the agent's dir)
            external_parent = str(Path(self.external_path).parent)
            path_added = False
            if external_parent not in sys.path:
                sys.path.insert(0, external_parent)
                path_added = True

            try:
                # Import as proper package
                # This will use __init__.py and maintain package namespace
                module = importlib.import_module(module_name)

                # Store module for hot-reload
                self._agent_modules[agent_name] = module
            finally:
                # Clean up sys.path
                if path_added and external_parent in sys.path:
                    sys.path.remove(external_parent)

            # Find Agent class
            if not hasattr(module, "Agent"):
                raise AttributeError(f"Module {agent_file} must define an 'Agent' class")

            agent_class = getattr(module, "Agent")
            return agent_class

        except Exception as e:
            logger.error(f"Error loading agent module {agent_name}: {e}", exc_info=True)
            return None

    def reload_agent(self, agent_name: str) -> type | None:
        """Reload an external agent (hot-reload for development).

        Args:
            agent_name: Name of the agent to reload

        Returns:
            Reloaded agent class if successful, None otherwise
        """
        if not self.external_path:
            logger.warning("Cannot reload: EXTERNAL_AGENTS_PATH not set")
            return None

        agent_dir = Path(self.external_path) / agent_name
        agent_file = agent_dir / "agent.py"

        if not agent_file.exists():
            logger.warning(f"Cannot reload {agent_name}: agent.py not found")
            return None

        try:
            # Remove from cache
            if agent_name in self._loaded_agents:
                del self._loaded_agents[agent_name]

            # Remove module from sys.modules
            module_name = f"external_agents.{agent_name}"
            if module_name in sys.modules:
                del sys.modules[module_name]

            # Reload
            agent_class = self._load_agent_module(agent_name, agent_file)
            if agent_class:
                self._loaded_agents[agent_name] = agent_class
                logger.info(f"♻️ Reloaded external agent: {agent_name}")
                return agent_class

        except Exception as e:
            logger.error(f"Failed to reload agent {agent_name}: {e}", exc_info=True)

        return None

    def get_agent_class(self, agent_name: str) -> type | None:
        """Get agent class by name.

        Args:
            agent_name: Name of the agent

        Returns:
            Agent class if found, None otherwise
        """
        return self._loaded_agents.get(agent_name)

    def list_external_agents(self) -> list[str]:
        """List all loaded external agent names.

        Returns:
            List of agent names
        """
        return list(self._loaded_agents.keys())


# Global loader instance
_external_loader: ExternalAgentLoader | None = None


def get_external_loader() -> ExternalAgentLoader:
    """Get or create global external agent loader."""
    global _external_loader
    if _external_loader is None:
        _external_loader = ExternalAgentLoader()
        # Auto-discover on first access
        _external_loader.discover_agents()
    return _external_loader


def reload_external_agent(agent_name: str) -> bool:
    """Reload an external agent (hot-reload for development).

    Args:
        agent_name: Name of the agent to reload

    Returns:
        True if reload successful, False otherwise
    """
    loader = get_external_loader()
    return loader.reload_agent(agent_name) is not None
