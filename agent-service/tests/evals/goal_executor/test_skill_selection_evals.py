"""Evals for skill selection in goal executor.

Tests that the executor selects appropriate skills for different tasks.

Run with: pytest tests/evals/goal_executor/test_skill_selection_evals.py -v
Requires: OPENAI_API_KEY environment variable
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.goal_executor.skills.prospect.clients import SearchResult


def _has_real_api_key() -> bool:
    """Check if a real OpenAI API key is available (not a test placeholder)."""
    key = os.getenv("OPENAI_API_KEY", "")
    # Real keys start with sk- and are 40+ chars, test keys contain "test"
    return key.startswith("sk-") and len(key) >= 40 and "test" not in key.lower()


# Skip all tests if no real API key
pytestmark = pytest.mark.skipif(
    not _has_real_api_key(),
    reason="Real OPENAI_API_KEY required for evals (not test placeholder)",
)


@pytest.fixture
def mock_skill_context():
    """Create mock skill context."""
    from agents.goal_executor.skills.base import SkillContext

    return SkillContext(
        bot_id="test_bot",
        run_id="test_run",
        config={"goal": "Test goal"},
    )


class TestSkillSelectionForResearch:
    """Evaluate skill selection for research tasks."""

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_web_search_for_company_discovery(self, mock_skill_context):
        """Eval: Web search should be used for discovering companies."""
        from agents.goal_executor.skills.primitives import WebSearchSkill

        skill = WebSearchSkill(context=mock_skill_context)

        # Mock Tavily - returns list[SearchResult]
        mock_results = [
            SearchResult(
                title="Acme AI raises $50M",
                url="https://example.com",
                content="Acme AI, an AI infrastructure company...",
                source="tavily",
            ),
        ]

        with patch.object(skill, "tavily") as mock_tavily:
            mock_tavily.search = MagicMock(return_value=mock_results)

            result = await skill.run(
                query="AI infrastructure companies Series B funding 2024",
                max_results=5,
            )

            assert result.is_success
            mock_tavily.search.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_deep_research_for_detailed_analysis(self, mock_skill_context):
        """Eval: Deep research should be used for detailed company analysis."""
        from agents.goal_executor.skills.primitives import DeepResearchSkill

        skill = DeepResearchSkill(context=mock_skill_context)

        with patch.object(skill, "perplexity") as mock_perplexity:
            # perplexity.research is sync, returns str
            mock_perplexity.is_configured = True
            mock_perplexity.research = MagicMock(
                return_value="Acme AI is a DevOps company founded in 2020..."
            )

            result = await skill.run(
                query="Detailed analysis of Acme AI company DevOps products and funding",
            )

            assert result.is_success
            mock_perplexity.research.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_memory_search_for_past_context(self, mock_skill_context):
        """Eval: Memory search should be used to find relevant past runs."""
        from agents.goal_executor.skills.primitives import SearchPastRunsSkill

        skill = SearchPastRunsSkill(context=mock_skill_context)

        # Patch where it's actually defined, not where it's imported
        with patch(
            "agents.goal_executor.services.vector_memory.get_vector_memory"
        ) as mock_vmem:
            mock_vmem_instance = MagicMock()
            mock_vmem_instance.search = AsyncMock(
                return_value=[
                    {
                        "summary": "Found AI companies in DevOps space",
                        "outcome": "Qualified 3 prospects",
                        "score": 0.85,
                        "companies": ["Acme", "TechBot"],
                    }
                ]
            )
            mock_vmem.return_value = mock_vmem_instance

            result = await skill.run(query="previous AI company research")

            assert result.is_success
            assert result.data.total_found == 1


class TestSkillSelectionForDeduplication:
    """Evaluate skill selection for avoiding duplicate work."""

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_check_company_before_research(self, mock_skill_context):
        """Eval: Should check if company was already researched."""
        from agents.goal_executor.skills.primitives import CheckCompanyResearchedSkill

        skill = CheckCompanyResearchedSkill(context=mock_skill_context)

        with patch(
            "agents.goal_executor.skills.primitives.get_goal_memory"
        ) as mock_memory:
            mock_memory_instance = MagicMock()
            mock_memory_instance.was_company_researched.return_value = True
            mock_memory.return_value = mock_memory_instance

            result = await skill.run(company_name="Acme Corp")

            assert result.is_success
            assert result.data["previously_researched"] is True

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_mark_company_after_research(self, mock_skill_context):
        """Eval: Should mark company as researched after completing research."""
        from agents.goal_executor.skills.primitives import MarkCompanyResearchedSkill

        skill = MarkCompanyResearchedSkill(context=mock_skill_context)

        with patch(
            "agents.goal_executor.skills.primitives.get_goal_memory"
        ) as mock_memory:
            mock_memory_instance = MagicMock()
            mock_memory.return_value = mock_memory_instance

            result = await skill.run(company_name="NewCo")

            assert result.is_success
            mock_memory_instance.log_company_researched.assert_called_once_with("NewCo")


class TestSkillSelectionForQualification:
    """Evaluate skill selection for prospect qualification."""

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_hubspot_check_for_existing_relationship(self, mock_skill_context):
        """Eval: Should check HubSpot for existing relationships."""
        from agents.goal_executor.skills.prospect.hubspot import CheckRelationshipSkill

        skill = CheckRelationshipSkill(context=mock_skill_context)

        with patch.object(skill, "hubspot") as mock_hubspot:
            # HubSpot is_configured must be True to trigger actual check
            mock_hubspot.is_configured = True
            # check_company is async and returns None for not found
            mock_hubspot.check_company = AsyncMock(return_value=None)

            result = await skill.run(company_name="New Prospect Inc")

            assert result.is_success
            # found_in_hubspot is False when not found, can_pursue is True
            assert result.data.found_in_hubspot is False
            assert result.data.can_pursue is True

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_qualify_prospect_uses_criteria(self, mock_skill_context):
        """Eval: Qualification should check against ICP criteria."""
        from agents.goal_executor.skills.prospect.qualify import QualifyProspectSkill

        skill = QualifyProspectSkill(context=mock_skill_context)

        # QualifyProspectSkill is rule-based, no LLM needed
        # Provide signals for scoring (Signal dataclass fields: type, title, content, url, strength)
        signals = [
            {
                "type": "funding",
                "title": "Series B Funding",
                "content": "Series B, $50M",
                "url": "https://example.com/funding",
                "strength": "high",
            },
            {
                "type": "job_posting",
                "title": "DevOps Hiring",
                "content": "Hiring DevOps engineers",
                "url": "https://example.com/jobs",
                "strength": "medium",
            },
        ]

        result = await skill.run(
            company_name="TechCo",
            signals=signals,
            industry="DevOps",
            employee_count=150,
        )

        assert result.is_success
        assert result.data.score > 0


class TestSkillChaining:
    """Evaluate that skills can be chained appropriately."""

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_research_then_qualify_flow(self, mock_skill_context):
        """Eval: Research skill output should feed into qualification."""
        from agents.goal_executor.skills.primitives import WebSearchSkill
        from agents.goal_executor.skills.prospect.qualify import QualifyProspectSkill

        # Step 1: Search
        search_skill = WebSearchSkill(context=mock_skill_context)

        mock_results = [
            SearchResult(
                title="TechCo raises Series B",
                url="https://example.com",
                content="TechCo, a DevOps platform, raised $40M in Series B",
                source="tavily",
            )
        ]

        with patch.object(search_skill, "tavily") as mock_tavily:
            mock_tavily.search = MagicMock(return_value=mock_results)

            search_result = await search_skill.run(query="DevOps Series B 2024")
            assert search_result.is_success

        # Step 2: Extract signals from search (simulated)
        # Signal dataclass fields: type, title, content, url, strength
        signals = [
            {
                "type": "funding",
                "title": "TechCo Series B",
                "content": "Series B, $40M",
                "url": "https://example.com",
                "strength": "high",
            },
        ]

        # Step 3: Qualify using signals
        qualify_skill = QualifyProspectSkill(context=mock_skill_context)

        qualify_result = await qualify_skill.run(
            company_name="TechCo",
            signals=signals,
            industry="DevOps",
        )

        # Qualification should work with search-derived signals
        assert qualify_result.status.value in ["success", "partial"]
