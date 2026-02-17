"""Base skill class and core types.

Skills are multi-step workflows that encapsulate complex operations.
They're more reliable than chaining multiple LLM tool calls because
the skill controls the execution flow internally.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SkillStatus(StrEnum):
    """Skill execution status."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # Some steps succeeded
    SKIPPED = "skipped"  # Skill determined work not needed


@dataclass
class SkillResult(Generic[T]):
    """Result from skill execution.

    Attributes:
        status: Execution status
        data: Result data (skill-specific type)
        message: Human-readable summary
        steps_completed: List of steps that ran
        error: Error message if failed
        duration_ms: Execution time in milliseconds
        metadata: Additional context
    """

    status: SkillStatus
    data: T | None = None
    message: str = ""
    steps_completed: list[str] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Check if skill succeeded."""
        return self.status == SkillStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        """Check if skill failed."""
        return self.status == SkillStatus.FAILED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "data": self.data,
            "message": self.message,
            "steps_completed": self.steps_completed,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        if self.is_success:
            return f"✅ {self.message}"
        elif self.is_failed:
            return f"❌ {self.error or self.message}"
        elif self.status == SkillStatus.SKIPPED:
            return f"⏭️ {self.message}"
        else:
            return f"⚠️ {self.message} (partial)"


@dataclass
class SkillContext:
    """Context passed to skill execution.

    Contains shared resources and state that skills can use.

    Attributes:
        bot_id: Goal bot identifier
        run_id: Current run identifier
        memory: Memory service for persistence
        cache: Cache for intermediate results
        config: Configuration dict
    """

    bot_id: str = "default"
    run_id: str = ""
    memory: Any = None  # GoalMemory instance
    cache: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)

    def get_cached(self, key: str) -> Any | None:
        """Get cached value."""
        return self.cache.get(key)

    def set_cached(self, key: str, value: Any) -> None:
        """Set cached value."""
        self.cache[key] = value


class BaseSkill(ABC):
    """Base class for all skills.

    Skills encapsulate multi-step workflows that would otherwise
    require multiple LLM tool calls. They provide:
    - Reliable execution (skill controls flow)
    - Composition (skills can call other skills)
    - Caching (skills can cache intermediate results)
    - Structured results (typed return values)

    Example:
        class ResearchProspectSkill(BaseSkill):
            name = "research_prospect"
            description = "Full prospect research workflow"

            async def execute(self, company_name: str) -> SkillResult[ProspectData]:
                # Step 1: Check HubSpot
                relationship = await self._check_hubspot(company_name)
                if relationship.is_customer:
                    return SkillResult(
                        status=SkillStatus.SKIPPED,
                        message=f"{company_name} is already a customer"
                    )

                # Step 2: Deep research
                profile = await self._research(company_name)

                # Step 3: Return result
                return SkillResult(
                    status=SkillStatus.SUCCESS,
                    data=ProspectData(company=company_name, profile=profile),
                    message=f"Researched {company_name}",
                    steps_completed=["hubspot_check", "research"]
                )
    """

    # Skill metadata (override in subclasses)
    name: str = "base_skill"
    description: str = "Base skill"
    version: str = "1.0.0"

    def __init__(self, context: SkillContext | None = None):
        """Initialize skill with context.

        Args:
            context: Shared context with memory, cache, etc.
        """
        self.context = context or SkillContext()
        self._start_time: datetime | None = None

    @abstractmethod
    async def execute(self, **kwargs: Any) -> SkillResult:
        """Execute the skill.

        Override this method to implement skill logic.

        Args:
            **kwargs: Skill-specific parameters

        Returns:
            SkillResult with status and data
        """
        pass

    async def run(self, **kwargs: Any) -> SkillResult:
        """Run the skill with timing and error handling.

        This is the main entry point - it wraps execute() with
        timing, logging, and error handling.

        Args:
            **kwargs: Skill-specific parameters

        Returns:
            SkillResult with status, data, and timing
        """
        self._start_time = datetime.now()
        logger.info(f"Starting skill: {self.name}")

        try:
            result = await self.execute(**kwargs)
            result.duration_ms = self._get_duration_ms()

            if result.is_success:
                logger.info(f"Skill {self.name} completed: {result.message}")
            elif result.is_failed:
                logger.error(f"Skill {self.name} failed: {result.error}")
            else:
                logger.info(f"Skill {self.name}: {result.message}")

            return result

        except Exception as e:
            logger.error(f"Skill {self.name} error: {e}", exc_info=True)
            return SkillResult(
                status=SkillStatus.FAILED,
                error=str(e),
                message=f"Skill {self.name} failed with error",
                duration_ms=self._get_duration_ms(),
            )

    def _get_duration_ms(self) -> int:
        """Get execution duration in milliseconds."""
        if not self._start_time:
            return 0
        delta = datetime.now() - self._start_time
        return int(delta.total_seconds() * 1000)

    def _step(self, name: str) -> None:
        """Log a step for debugging."""
        logger.debug(f"[{self.name}] Step: {name}")

    async def _invoke_skill(self, skill_name: str, **kwargs: Any) -> SkillResult:
        """Invoke another skill by name.

        Skills can compose other skills for complex workflows.

        Args:
            skill_name: Name of skill to invoke
            **kwargs: Parameters for the skill

        Returns:
            SkillResult from invoked skill
        """
        from .registry import get_skill_registry

        registry = get_skill_registry()
        skill_class = registry.get(skill_name)

        if not skill_class:
            return SkillResult(
                status=SkillStatus.FAILED,
                error=f"Skill '{skill_name}' not found",
            )

        skill = skill_class(context=self.context)
        return await skill.run(**kwargs)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name})>"
