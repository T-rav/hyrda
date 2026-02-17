"""Full prospect research skill - the main workflow.

This skill combines all the other skills into a complete
prospect research workflow:
1. Check HubSpot relationship
2. Search for signals
3. Deep company research
4. Qualify and score
5. Save qualified prospect
"""

from dataclasses import dataclass
from typing import Any

from ...services.memory import get_goal_memory
from ..base import BaseSkill, SkillContext, SkillResult, SkillStatus
from .clients import get_perplexity
from .hubspot import CheckRelationshipSkill, RelationshipData
from .qualify import QualificationData, QualifyProspectSkill
from .signals import SearchSignalsSkill, SignalSearchData


@dataclass
class ProspectResearchData:
    """Complete prospect research result."""

    company_name: str
    relationship: RelationshipData | None = None
    signals: SignalSearchData | None = None
    qualification: QualificationData | None = None
    deep_research: str | None = None
    saved: bool = False
    prospect_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_name": self.company_name,
            "relationship": self.relationship.to_dict() if self.relationship else None,
            "signals": self.signals.to_dict() if self.signals else None,
            "qualification": self.qualification.to_dict()
            if self.qualification
            else None,
            "deep_research": self.deep_research[:500] if self.deep_research else None,
            "saved": self.saved,
            "prospect_id": self.prospect_id,
        }


class ResearchProspectSkill(BaseSkill):
    """Complete prospect research workflow.

    This is the main skill that orchestrates a full prospect
    research workflow:

    1. Check HubSpot - Skip if existing customer/deal
    2. Search signals - Find buying signals across sources
    3. Deep research - Perplexity company research
    4. Qualify - Score and prioritize
    5. Save - Persist qualified prospects to MinIO

    This replaces multiple LLM tool calls with a single
    reliable workflow.
    """

    name = "research_prospect"
    description = "Complete prospect research workflow (HubSpot + signals + research + qualify + save)"
    version = "1.0.0"

    def __init__(self, context: SkillContext | None = None):
        super().__init__(context)
        self.perplexity = get_perplexity()

    async def execute(
        self,
        company_name: str,
        signal_types: list[str] | None = None,
        skip_if_in_hubspot: bool = True,
        auto_save: bool = True,
        min_score_to_save: int = 40,
    ) -> SkillResult[ProspectResearchData]:
        """Research a prospect company.

        Args:
            company_name: Company to research
            signal_types: Signal types to search (default: jobs, news, funding)
            skip_if_in_hubspot: Skip if existing customer/deal
            auto_save: Automatically save qualified prospects
            min_score_to_save: Minimum score to auto-save

        Returns:
            SkillResult with complete research data
        """
        data = ProspectResearchData(company_name=company_name)

        # Step 1: Check HubSpot relationship
        self._step("check_relationship")
        relationship_skill = CheckRelationshipSkill(context=self.context)
        relationship_result = await relationship_skill.run(company_name=company_name)

        if relationship_result.data:
            data.relationship = relationship_result.data

            # Skip if existing customer/deal and flag is set
            if skip_if_in_hubspot and not relationship_result.data.can_pursue:
                return SkillResult(
                    status=SkillStatus.SKIPPED,
                    data=data,
                    message=f"⏭️ Skipped {company_name}: {relationship_result.data.skip_reason}",
                    steps_completed=["check_relationship"],
                )

        # Step 2: Search for signals
        self._step("search_signals")
        signals_skill = SearchSignalsSkill(context=self.context)
        signals_result = await signals_skill.run(
            query=company_name,
            signal_types=signal_types or ["jobs", "news", "funding"],
        )

        if signals_result.data:
            data.signals = signals_result.data

        # Step 3: Deep research (if we have Perplexity)
        if self.perplexity.is_configured:
            self._step("deep_research")
            research_prompt = (
                f"Research {company_name}: What they do, company size, "
                "technology stack, recent news, funding history, and key leadership."
            )
            data.deep_research = self.perplexity.research(research_prompt)

        # Step 4: Qualify prospect
        self._step("qualify")
        qualify_skill = QualifyProspectSkill(context=self.context)

        # Get employee count from relationship data if available
        employee_count = None
        industry = None
        if data.relationship and data.relationship.company_info:
            employee_count = data.relationship.company_info.employees
            industry = data.relationship.company_info.industry

        # Pass signals as dicts
        signal_dicts = []
        if data.signals:
            signal_dicts = [s.to_dict() for s in data.signals.signals]

        qualify_result = await qualify_skill.run(
            company_name=company_name,
            signals=signal_dicts,
            employee_count=employee_count,
            industry=industry,
        )

        if qualify_result.data:
            data.qualification = qualify_result.data

        # Step 5: Save if qualified and auto_save enabled
        if (
            auto_save
            and data.qualification
            and data.qualification.is_qualified
            and data.qualification.score >= min_score_to_save
        ):
            self._step("save_prospect")
            memory = get_goal_memory(self.context.bot_id)

            prospect_record = {
                "company_name": company_name,
                "score": data.qualification.score,
                "priority": data.qualification.priority,
                "signal_sources": data.qualification.signals_used,
                "notes": self._build_notes(data),
                "recommended_approach": data.qualification.recommended_approach,
            }

            prospect_id = memory.save_prospect(prospect_record)
            if prospect_id:
                data.saved = True
                data.prospect_id = prospect_id

        # Build final result
        steps = ["check_relationship", "search_signals"]
        if data.deep_research:
            steps.append("deep_research")
        steps.append("qualify")
        if data.saved:
            steps.append("save_prospect")

        if data.qualification and data.qualification.is_qualified:
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                data.qualification.priority, "⚪"
            )
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=data,
                message=(
                    f"{emoji} {company_name}: {data.qualification.score}/100 "
                    f"({data.qualification.priority} priority)"
                    + (f" - Saved as {data.prospect_id}" if data.saved else "")
                ),
                steps_completed=steps,
            )
        else:
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=data,
                message=f"❌ {company_name}: Not qualified (score: {data.qualification.score if data.qualification else 0})",
                steps_completed=steps,
            )

    def _build_notes(self, data: ProspectResearchData) -> str:
        """Build notes from research data."""
        notes = []

        if data.qualification:
            if data.qualification.strengths:
                notes.append("Strengths: " + "; ".join(data.qualification.strengths))
            if data.qualification.weaknesses:
                notes.append("Concerns: " + "; ".join(data.qualification.weaknesses))

        if data.signals and data.signals.signals:
            signal_summary = ", ".join(
                f"{s.type}: {s.title[:50]}" for s in data.signals.signals[:3]
            )
            notes.append(f"Signals: {signal_summary}")

        if data.deep_research:
            notes.append(f"Research: {data.deep_research[:300]}...")

        return "\n".join(notes)
