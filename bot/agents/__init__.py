"""Agent routing (HTTP-based, no local agent classes)."""

from agents.registry import agent_registry
from agents.router import command_router

__all__ = ["agent_registry", "command_router"]
