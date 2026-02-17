"""Prospect research skills.

These skills encapsulate the multi-step workflows for prospect research:
- Research a prospect (HubSpot + web + scoring)
- Search for signals (jobs, news, funding)
- Qualify a prospect
- Check relationships
"""

# Register all skills on import
from ..registry import register_skill
from .hubspot import CheckRelationshipSkill
from .qualify import QualifyProspectSkill
from .research import ResearchProspectSkill
from .signals import SearchSignalsSkill

register_skill(ResearchProspectSkill)
register_skill(SearchSignalsSkill)
register_skill(QualifyProspectSkill)
register_skill(CheckRelationshipSkill)

__all__ = [
    "ResearchProspectSkill",
    "SearchSignalsSkill",
    "QualifyProspectSkill",
    "CheckRelationshipSkill",
]
