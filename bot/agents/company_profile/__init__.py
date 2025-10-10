"""Company Profile Deep Research Package.

LangGraph-based deep research system for generating comprehensive
company, employee, and project profiles.
"""

from agents.company_profile.configuration import ProfileConfiguration, SearchAPI
from agents.company_profile.state import (
    ClarifyWithUser,
    ConductResearch,
    ProfileAgentInputState,
    ProfileAgentState,
    ProfileResearchBrief,
    ResearchComplete,
    ResearcherOutputState,
    ResearcherState,
    SupervisorState,
)

__all__ = [
    # Configuration
    "ProfileConfiguration",
    "SearchAPI",
    # State classes
    "ProfileAgentState",
    "ProfileAgentInputState",
    "SupervisorState",
    "ResearcherState",
    "ResearcherOutputState",
    # Structured outputs
    "ClarifyWithUser",
    "ConductResearch",
    "ResearchComplete",
    "ProfileResearchBrief",
]
