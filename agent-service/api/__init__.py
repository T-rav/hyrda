"""API routers for agent service."""

from api.agents import router as agents_router
from api.goal_bots import router as goal_bots_router

__all__ = ["agents_router", "goal_bots_router"]
