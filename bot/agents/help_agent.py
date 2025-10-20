"""Help Agent - List available agents and commands.

Provides information about available bot agents and their usage.
"""

import logging
from typing import Any

from agents.base_agent import BaseAgent
from agents.registry import agent_registry

logger = logging.getLogger(__name__)


class HelpAgent(BaseAgent):
    """Agent for listing available bot agents and their aliases.

    Handles queries like:
    - "-agents" - List all available agents
    - "-help" - Show help information
    """

    name = "agents"
    aliases = ["help"]
    description = "List available bot agents and their aliases"

    def __init__(self):
        """Initialize HelpAgent."""
        super().__init__()

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        """List all registered agents.

        Args:
            query: User query (ignored for this agent)
            context: Context dict with user_id, channel, slack_service, etc.

        Returns:
            Result dict with response text listing all agents
        """
        if not self.validate_context(context):
            return {
                "response": "❌ Invalid context for help agent",
                "metadata": {"error": "missing_context"},
            }

        logger.info("HelpAgent listing all available agents")

        # Get all registered agents
        agents = agent_registry.list_agents()

        # Build response
        response_lines = [
            "🤖 **Available Bot Agents**\n",
            "Use these commands to interact with specialized agents:\n",
        ]

        for agent_info in sorted(agents, key=lambda x: x["name"]):
            agent_name = agent_info["name"]
            agent_class = agent_info["agent_class"]
            aliases = agent_info["aliases"]

            # Get description from agent class
            description = getattr(
                agent_class, "description", "No description available"
            )

            # Format agent line
            agent_line = f"\n**-{agent_name}**"
            if aliases:
                alias_text = ", ".join([f"-{alias}" for alias in aliases])
                agent_line += f" (aliases: {alias_text})"

            response_lines.append(agent_line)
            response_lines.append(f"  {description}")

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
            "metadata": {
                "agent": "help",
                "agent_count": len(agents),
            },
        }


# Register agent with registry
agent_registry.register(
    name=HelpAgent.name,
    agent_class=HelpAgent,
    aliases=HelpAgent.aliases,
)

logger.info(f"HelpAgent registered: -{HelpAgent.name} (aliases: {HelpAgent.aliases})")
