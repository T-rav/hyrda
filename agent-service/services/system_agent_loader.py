"""System agent loader - loads agents from agents/system/ directory.

System agents are LangGraph workflows baked into the Docker image (not volume-mounted).
These are framework-level agents that ship with every deployment.
"""

import importlib
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SystemAgentLoader:
    """Loads system agents from agents/system/ directory.

    System agents are LangGraph workflows embedded in the image, following
    the same pattern as external agents but shipped with the framework.
    """

    def __init__(self, system_agents_path: str | None = None):
        """Initialize system agent loader.

        Args:
            system_agents_path: Path to system agents directory
                              (default: agents/system relative to project root)
        """
        if system_agents_path:
            self.system_agents_path = Path(system_agents_path)
        else:
            # Default: agents/system relative to this file
            self.system_agents_path = Path(__file__).parent.parent / "agents" / "system"

        self._loaded_agents: dict[str, Any] = {}
        logger.info(f"SystemAgentLoader initialized: {self.system_agents_path}")

    def discover_agents(self) -> dict[str, Any]:
        """Discover and load all system agents.

        Scans agents/system/ directory for agent subdirectories.
        Each subdirectory should have agent.py with Agent export.

        Returns:
            Dict mapping agent names to Agent classes/instances
        """
        if self._loaded_agents:
            return self._loaded_agents

        if not self.system_agents_path.exists():
            logger.warning(f"System agents path not found: {self.system_agents_path}")
            return {}

        agents = {}

        # Scan subdirectories in agents/system/
        for agent_dir in self.system_agents_path.iterdir():
            if not agent_dir.is_dir():
                continue

            agent_name = agent_dir.name

            # Skip special directories
            if agent_name.startswith("_") or agent_name.startswith("."):
                continue

            # Check for agent.py
            agent_file = agent_dir / "agent.py"
            if not agent_file.exists():
                logger.debug(f"Skipping {agent_name}: no agent.py found")
                continue

            # Load agent module
            try:
                agent_class = self._load_agent_module(agent_name)
                if agent_class:
                    agents[agent_name] = agent_class
                    logger.info(f"✅ Loaded system agent: {agent_name}")
            except Exception as e:
                logger.error(f"❌ Error loading system agent {agent_name}: {e}")

        self._loaded_agents = agents
        logger.info(f"Discovered {len(agents)} system agent(s)")
        return agents

    def _load_agent_module(self, agent_name: str) -> Any:
        """Load agent module and extract Agent class/instance.

        Uses proper package imports: agents.system.{agent_name}.agent

        Args:
            agent_name: Name of agent subdirectory

        Returns:
            Agent class or instance, or None if not found
        """
        try:
            # Add agents parent directory to sys.path if not already there
            agents_parent = self.system_agents_path.parent.parent
            if str(agents_parent) not in sys.path:
                sys.path.insert(0, str(agents_parent))

            # Import as proper package: agents.system.{agent_name}.agent
            module_name = f"agents.system.{agent_name}.agent"
            module = importlib.import_module(module_name)

            # Look for Agent attribute (class or instance)
            if hasattr(module, "Agent"):
                agent = module.Agent
                logger.debug(f"Found Agent in {module_name}: {type(agent)}")
                return agent
            else:
                logger.warning(f"No Agent attribute found in {module_name}")
                return None

        except ImportError as e:
            logger.error(f"Import error loading {agent_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading {agent_name}: {e}", exc_info=True)
            return None

    def get_agent(self, agent_name: str) -> Any:
        """Get specific system agent by name.

        Args:
            agent_name: Agent name

        Returns:
            Agent class/instance or None if not found
        """
        if not self._loaded_agents:
            self.discover_agents()

        return self._loaded_agents.get(agent_name)

    def reload_agent(self, agent_name: str) -> Any:
        """Reload a specific system agent.

        Useful for development when agent code changes.

        Args:
            agent_name: Agent name to reload

        Returns:
            Reloaded agent or None if failed
        """
        # Clear from cache
        if agent_name in self._loaded_agents:
            del self._loaded_agents[agent_name]

        # Reload module
        try:
            module_name = f"agents.system.{agent_name}.agent"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])

            # Load again
            agent = self._load_agent_module(agent_name)
            if agent:
                self._loaded_agents[agent_name] = agent
                logger.info(f"♻️ Reloaded system agent: {agent_name}")
                return agent
        except Exception as e:
            logger.error(f"Error reloading system agent {agent_name}: {e}")

        return None

    def list_system_agents(self) -> list[str]:
        """List all available system agent names.

        Returns:
            List of system agent names
        """
        if not self._loaded_agents:
            self.discover_agents()

        return list(self._loaded_agents.keys())


# Global singleton instance
_system_loader: SystemAgentLoader | None = None


def get_system_loader(system_agents_path: str | None = None) -> SystemAgentLoader:
    """Get global system agent loader instance.

    Args:
        system_agents_path: Optional override for system agents path

    Returns:
        System agent loader singleton
    """
    global _system_loader
    if _system_loader is None:
        _system_loader = SystemAgentLoader(system_agents_path)
    return _system_loader


def reload_system_agent(agent_name: str) -> Any:
    """Reload a specific system agent.

    Convenience function for development.

    Args:
        agent_name: Agent name to reload

    Returns:
        Reloaded agent or None
    """
    loader = get_system_loader()
    return loader.reload_agent(agent_name)
