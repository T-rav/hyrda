"""Skills framework for goal executor agents.

Skills are higher-level abstractions than tools - they encapsulate
multi-step workflows that would otherwise require multiple LLM tool calls.

Based on the OpenClaw pattern:
- Skills are registered in a registry
- Each skill has a name, description, and async execute method
- Skills can compose other skills or use low-level clients
- Skills return structured results

Available Skills:
    Workflows (bundled multi-step):
    - research_prospect: Full prospect research workflow
    - search_signals: Multi-source signal search
    - check_relationship: HubSpot relationship check
    - qualify_prospect: Score and qualify prospects

    Primitives (direct access):
    - web_search: Direct Tavily web search
    - deep_research: Direct Perplexity research
    - recall_memory: Search/recall from persistent memory
    - save_memory: Save to persistent memory
    - list_prospects: List saved prospects
    - get_run_history: Get recent run history
"""

# Import primitives and youtube to register them
from . import (
    primitives,  # noqa: F401
    youtube,  # noqa: F401
)
from .base import BaseSkill, SkillContext, SkillResult, SkillStatus
from .executor import SkillExecutor
from .registry import SkillRegistry, get_skill_registry, register_skill

__all__ = [
    "BaseSkill",
    "SkillResult",
    "SkillContext",
    "SkillStatus",
    "SkillRegistry",
    "get_skill_registry",
    "register_skill",
    "SkillExecutor",
]
