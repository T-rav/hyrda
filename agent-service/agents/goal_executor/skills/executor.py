"""Skill executor for running skills from LLM tool calls.

The executor bridges LangGraph tools and skills - it provides
a tool that the LLM can call to invoke any registered skill.
"""

import json
import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from .base import SkillContext, SkillResult
from .registry import get_skill_registry

logger = logging.getLogger(__name__)


class SkillInvocation(BaseModel):
    """Input schema for skill invocation."""

    skill_name: str = Field(..., description="Name of the skill to invoke")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters to pass to the skill",
    )


class SkillExecutor(BaseTool):
    """LangGraph tool that executes registered skills.

    This allows the LLM to invoke any registered skill by name,
    providing a single tool interface for all skills.

    Example:
        # Register skills
        registry = get_skill_registry()
        registry.register(ResearchProspectSkill)
        registry.register(SearchSignalsSkill)

        # Create executor tool
        executor = SkillExecutor(context=ctx)

        # LLM can now call skills:
        # invoke_skill(skill_name="research_prospect", parameters={"company": "Acme"})
    """

    name: str = "invoke_skill"
    description: str = """Invoke a registered skill to perform a multi-step workflow.

Available skills will be listed in the response if skill_name is invalid.

Skills are more reliable than chaining multiple tool calls because they
handle the workflow internally with proper error handling and caching.

Common skills:
- research_prospect: Full prospect research (HubSpot check + web research + scoring)
- search_signals: Multi-source signal search (jobs, news, funding)
- qualify_prospect: Score and qualify a prospect based on signals
- check_relationship: Check HubSpot for existing relationship

Parameters are skill-specific - check skill documentation for required params."""

    args_schema: type[BaseModel] = SkillInvocation
    context: SkillContext | None = None

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True

    def __init__(self, context: SkillContext | None = None, **kwargs: Any):
        """Initialize executor with context.

        Args:
            context: Shared context for skills
            **kwargs: Additional BaseTool arguments
        """
        super().__init__(**kwargs)
        self.context = context or SkillContext()

    def _run(self, skill_name: str, parameters: dict[str, Any] | None = None) -> str:
        """Synchronous execution (calls async internally).

        Args:
            skill_name: Name of skill to invoke
            parameters: Skill parameters

        Returns:
            String result for LLM
        """
        import asyncio

        params = parameters or {}

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context, create new loop
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self._execute_skill(skill_name, params)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self._execute_skill(skill_name, params))
        except Exception as e:
            logger.error(f"Skill execution error: {e}", exc_info=True)
            return f"❌ Skill execution failed: {e}"

    async def _arun(
        self, skill_name: str, parameters: dict[str, Any] | None = None
    ) -> str:
        """Async execution.

        Args:
            skill_name: Name of skill to invoke
            parameters: Skill parameters

        Returns:
            String result for LLM
        """
        return await self._execute_skill(skill_name, parameters or {})

    async def _execute_skill(self, skill_name: str, parameters: dict[str, Any]) -> str:
        """Execute a skill and format result.

        Args:
            skill_name: Name of skill
            parameters: Skill parameters

        Returns:
            Formatted result string
        """
        registry = get_skill_registry()

        # Check if skill exists
        skill_class = registry.get(skill_name)
        if not skill_class:
            available = registry.get_skill_names()
            return (
                f"❌ Skill '{skill_name}' not found.\n\n"
                f"Available skills:\n" + "\n".join(f"  - {name}" for name in available)
            )

        # Instantiate and run skill
        skill = skill_class(context=self.context)
        result = await skill.run(**parameters)

        # Format result for LLM
        return self._format_result(skill_name, result)

    def _format_result(self, skill_name: str, result: SkillResult) -> str:
        """Format skill result for LLM consumption.

        Args:
            skill_name: Name of skill that ran
            result: Skill result

        Returns:
            Formatted string
        """
        output = [f"**Skill: {skill_name}**"]
        output.append(str(result))

        if result.steps_completed:
            output.append(f"\nSteps: {' → '.join(result.steps_completed)}")

        if result.data:
            # Format data based on type
            if isinstance(result.data, dict):
                data_str = json.dumps(result.data, indent=2, default=str)
                output.append(f"\n**Data:**\n```json\n{data_str}\n```")
            elif hasattr(result.data, "to_dict"):
                data_str = json.dumps(result.data.to_dict(), indent=2, default=str)
                output.append(f"\n**Data:**\n```json\n{data_str}\n```")
            else:
                output.append(f"\n**Data:** {result.data}")

        if result.duration_ms:
            output.append(f"\n⏱️ Duration: {result.duration_ms}ms")

        return "\n".join(output)


def create_skill_tools(context: SkillContext | None = None) -> list[BaseTool]:
    """Create LangGraph tools for all registered skills.

    This creates individual tools for each skill (more discoverable)
    plus the generic invoke_skill tool.

    Args:
        context: Shared context for skills

    Returns:
        List of BaseTool instances
    """
    ctx = context or SkillContext()
    tools: list[BaseTool] = []

    # Add the generic executor
    tools.append(SkillExecutor(context=ctx))

    # Could also create individual tools per skill here if needed
    # for name, skill_class in get_skill_registry()._skills.items():
    #     tools.append(create_tool_for_skill(skill_class, ctx))

    return tools
