"""Skill registry for discovering and invoking skills.

Skills are registered by name and can be looked up dynamically.
This allows skills to invoke other skills without tight coupling.
"""

import logging

from .base import BaseSkill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Registry for discovering and managing skills.

    Skills register themselves with a unique name. Other code can
    look up skills by name to invoke them dynamically.

    Example:
        registry = SkillRegistry()
        registry.register(ResearchProspectSkill)
        registry.register(SearchSignalsSkill)

        # Later, invoke by name
        skill_class = registry.get("research_prospect")
        skill = skill_class(context=ctx)
        result = await skill.run(company_name="Acme")
    """

    def __init__(self):
        """Initialize empty registry."""
        self._skills: dict[str, type[BaseSkill]] = {}

    def register(self, skill_class: type[BaseSkill]) -> None:
        """Register a skill class.

        Args:
            skill_class: Skill class to register

        Raises:
            ValueError: If skill name conflicts with existing
        """
        name = skill_class.name

        if name in self._skills:
            existing = self._skills[name]
            if existing != skill_class:
                logger.warning(
                    f"Skill '{name}' already registered by {existing.__name__}, "
                    f"overwriting with {skill_class.__name__}"
                )

        self._skills[name] = skill_class
        logger.debug(f"Registered skill: {name} -> {skill_class.__name__}")

    def get(self, name: str) -> type[BaseSkill] | None:
        """Get a skill class by name.

        Args:
            name: Skill name

        Returns:
            Skill class or None if not found
        """
        return self._skills.get(name)

    def list_skills(self) -> list[dict[str, str]]:
        """List all registered skills.

        Returns:
            List of skill info dicts with name, description, version
        """
        return [
            {
                "name": skill_class.name,
                "description": skill_class.description,
                "version": skill_class.version,
            }
            for skill_class in self._skills.values()
        ]

    def get_skill_names(self) -> list[str]:
        """Get list of registered skill names.

        Returns:
            List of skill names
        """
        return list(self._skills.keys())

    def __contains__(self, name: str) -> bool:
        """Check if skill is registered."""
        return name in self._skills

    def __len__(self) -> int:
        """Get number of registered skills."""
        return len(self._skills)


# Global registry instance
_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry.

    Returns:
        Shared SkillRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def register_skill(skill_class: type[BaseSkill]) -> type[BaseSkill]:
    """Decorator to register a skill class.

    Example:
        @register_skill
        class MySkill(BaseSkill):
            name = "my_skill"
            ...

    Args:
        skill_class: Skill class to register

    Returns:
        Same skill class (for decorator chaining)
    """
    get_skill_registry().register(skill_class)
    return skill_class
