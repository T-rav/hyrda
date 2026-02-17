"""Prospect qualification skill - score and qualify prospects."""

from dataclasses import dataclass, field
from typing import Any

from ..base import BaseSkill, SkillResult, SkillStatus
from .signals import Signal


@dataclass
class QualificationData:
    """Prospect qualification result."""

    company_name: str
    score: int  # 0-100
    priority: str  # high, medium, low
    is_qualified: bool
    signals_used: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    recommended_approach: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_name": self.company_name,
            "score": self.score,
            "priority": self.priority,
            "is_qualified": self.is_qualified,
            "signals_used": self.signals_used,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommended_approach": self.recommended_approach,
        }


# Scoring weights
SIGNAL_WEIGHTS = {
    "funding": 25,
    "job_posting": 20,
    "news": 15,
    "competitor": 10,
    "research": 10,
}

SIGNAL_STRENGTH_MULTIPLIER = {
    "high": 1.5,
    "medium": 1.0,
    "low": 0.5,
}


class QualifyProspectSkill(BaseSkill):
    """Score and qualify a prospect based on signals.

    This skill takes signals found for a company and produces
    a qualification score with priority and recommendations.

    Scoring:
    - 80-100: High priority (strong signals, clear fit)
    - 60-79: Medium priority (multiple signals)
    - 40-59: Low priority (weak signals)
    - Below 40: Not qualified

    The skill also provides:
    - Strengths (why they're a good fit)
    - Weaknesses (concerns)
    - Recommended outreach approach
    """

    name = "qualify_prospect"
    description = "Score and qualify a prospect based on signals"
    version = "1.0.0"

    async def execute(
        self,
        company_name: str,
        signals: list[dict[str, Any]],
        employee_count: int | None = None,
        industry: str | None = None,
    ) -> SkillResult[QualificationData]:
        """Qualify a prospect.

        Args:
            company_name: Company to qualify
            signals: List of signal dicts (from SearchSignalsSkill)
            employee_count: Optional employee count
            industry: Optional industry

        Returns:
            SkillResult with qualification data
        """
        self._step("calculate_score")

        # Convert signal dicts to Signal objects if needed
        signal_objects = [Signal(**s) if isinstance(s, dict) else s for s in signals]

        # Calculate base score from signals
        score = self._calculate_signal_score(signal_objects)

        # Adjust for company size (ICP: 100-5000 employees)
        if employee_count:
            self._step("size_adjustment")
            if 100 <= employee_count <= 5000:
                score += 10  # Perfect size
            elif 50 <= employee_count < 100 or 5000 < employee_count <= 10000:
                score += 5  # Acceptable size
            # Larger or smaller gets no bonus

        # Adjust for industry fit
        if industry:
            self._step("industry_adjustment")
            good_industries = [
                "technology",
                "software",
                "fintech",
                "healthtech",
                "ai",
                "saas",
            ]
            if any(ind in industry.lower() for ind in good_industries):
                score += 5

        # Cap score at 100
        score = min(score, 100)

        # Determine priority
        if score >= 80:
            priority = "high"
            is_qualified = True
        elif score >= 60:
            priority = "medium"
            is_qualified = True
        elif score >= 40:
            priority = "low"
            is_qualified = True
        else:
            priority = "none"
            is_qualified = False

        # Build strengths/weaknesses
        strengths, weaknesses = self._analyze_fit(
            signal_objects, employee_count, industry
        )

        # Generate recommended approach
        recommended_approach = self._generate_approach(signal_objects, strengths)

        data = QualificationData(
            company_name=company_name,
            score=score,
            priority=priority,
            is_qualified=is_qualified,
            signals_used=[s.type for s in signal_objects],
            strengths=strengths,
            weaknesses=weaknesses,
            recommended_approach=recommended_approach,
        )

        if is_qualified:
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=data,
                message=f"✅ {company_name} qualified: {score}/100 ({priority} priority)",
                steps_completed=["calculate_score", "analyze_fit", "generate_approach"],
            )
        else:
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=data,
                message=f"❌ {company_name} not qualified: {score}/100",
                steps_completed=["calculate_score", "analyze_fit"],
            )

    def _calculate_signal_score(self, signals: list[Signal]) -> int:
        """Calculate score from signals."""
        if not signals:
            return 0

        score = 0
        for signal in signals:
            base_weight = SIGNAL_WEIGHTS.get(signal.type, 5)
            multiplier = SIGNAL_STRENGTH_MULTIPLIER.get(signal.strength, 1.0)
            score += int(base_weight * multiplier)

        return min(score, 70)  # Signals alone cap at 70

    def _analyze_fit(
        self,
        signals: list[Signal],
        employee_count: int | None,
        industry: str | None,
    ) -> tuple[list[str], list[str]]:
        """Analyze strengths and weaknesses."""
        strengths = []
        weaknesses = []

        # Signal analysis
        signal_types = {s.type for s in signals}
        high_signals = [s for s in signals if s.strength == "high"]

        if "funding" in signal_types:
            strengths.append("Recent funding indicates budget availability")
        if "job_posting" in signal_types:
            strengths.append("Active hiring shows growth/investment")
        if high_signals:
            strengths.append(f"{len(high_signals)} high-strength signals")

        if not signals:
            weaknesses.append("No buying signals found")
        if len(signals) < 2:
            weaknesses.append("Limited signal coverage")

        # Size analysis
        if employee_count:
            if 100 <= employee_count <= 5000:
                strengths.append(f"Ideal company size ({employee_count} employees)")
            elif employee_count < 50:
                weaknesses.append("Company may be too small")
            elif employee_count > 10000:
                weaknesses.append("Large enterprise - longer sales cycle")

        # Industry analysis
        if industry:
            good_industries = ["technology", "software", "fintech", "healthtech", "ai"]
            if any(ind in industry.lower() for ind in good_industries):
                strengths.append(f"Target industry: {industry}")
            else:
                weaknesses.append(f"Industry ({industry}) may not be ideal fit")

        return strengths, weaknesses

    def _generate_approach(self, signals: list[Signal], strengths: list[str]) -> str:
        """Generate recommended outreach approach."""
        approaches = []

        signal_types = {s.type for s in signals}

        if "funding" in signal_types:
            approaches.append("Reference recent funding and growth trajectory")

        if "job_posting" in signal_types:
            approaches.append("Connect hiring needs to our services")

        if "news" in signal_types:
            approaches.append("Reference recent company news/announcements")

        if not approaches:
            approaches.append("Standard value proposition outreach")

        if "Ideal company size" in " ".join(strengths):
            approaches.append("Emphasize mid-market focus and agility")

        return ". ".join(approaches) + "."
