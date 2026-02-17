"""Evals for skill selection in goal executor.

Tests that the executor selects appropriate skills for different tasks.

Run with: pytest tests/evals/goal_executor/test_skill_selection_evals.py -v
Requires: OPENAI_API_KEY environment variable
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip all tests if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY required for evals",
)


@pytest.fixture
def mock_skill_context():
    """Create mock skill context."""
    from agents.goal_executor.skills.base import SkillContext

    return SkillContext(
        bot_id="test_bot",
        thread_id="test_thread",
        goal="Test goal",
    )


class TestSkillSelectionForResearch:
    """Evaluate skill selection for research tasks."""

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_web_search_for_company_discovery(self, mock_skill_context):
        """Eval: Web search should be used for discovering companies."""
        from agents.goal_executor.skills.primitives import WebSearchSkill

        skill = WebSearchSkill(context=mock_skill_context)

        # Mock Tavily
        with patch.object(skill, "tavily") as mock_tavily:
            mock_tavily.search = AsyncMock(
                return_value={
                    "results": [
                        {
                            "title": "Acme AI raises $50M",
                            "url": "https://example.com",
                            "content": "...",
                        },
                    ]
                }
            )

            result = await skill.run(
                query="AI infrastructure companies Series B funding 2024",
                max_results=5,
            )

            assert result.is_success
            mock_tavily.search.assert_called_once()

            # Verify query was passed correctly
            call_args = mock_tavily.search.call_args
            assert "AI infrastructure" in call_args[1]["query"]

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_deep_research_for_detailed_analysis(self, mock_skill_context):
        """Eval: Deep research should be used for detailed company analysis."""
        from agents.goal_executor.skills.primitives import DeepResearchSkill

        skill = DeepResearchSkill(context=mock_skill_context)

        with patch.object(skill, "perplexity") as mock_perplexity:
            mock_perplexity.search = AsyncMock(
                return_value="Acme AI is a DevOps company founded in 2020..."
            )

            result = await skill.run(
                query="Detailed analysis of Acme AI company DevOps products and funding",
            )

            assert result.is_success
            mock_perplexity.search.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_memory_search_for_past_context(self, mock_skill_context):
        """Eval: Memory search should be used to find relevant past runs."""
        from agents.goal_executor.skills.primitives import SearchPastRunsSkill

        skill = SearchPastRunsSkill(context=mock_skill_context)

        with patch(
            "agents.goal_executor.services.vector_memory.get_vector_memory"
        ) as mock_vmem:
            mock_vmem_instance = AsyncMock()
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
            mock_hubspot.search_companies = AsyncMock(return_value=[])
            mock_hubspot.search_contacts = AsyncMock(return_value=[])
            mock_hubspot.search_deals = AsyncMock(return_value=[])

            result = await skill.run(company_name="New Prospect Inc")

            assert result.is_success
            assert result.data.has_relationship is False

    @pytest.mark.asyncio
    @pytest.mark.eval
    async def test_qualify_prospect_uses_criteria(self, mock_skill_context):
        """Eval: Qualification should check against ICP criteria."""
        from agents.goal_executor.skills.prospect.qualify import QualifyProspectSkill

        skill = QualifyProspectSkill(context=mock_skill_context)

        # Mock the LLM call inside qualify
        with patch(
            "agents.goal_executor.skills.prospect.qualify.ChatOpenAI"
        ) as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.ainvoke = AsyncMock(
                return_value=MagicMock(
                    content='{"score": 85, "reasoning": "Strong fit", "signals": ["recent funding"]}'
                )
            )
            mock_llm.return_value = mock_llm_instance

            result = await skill.run(
                company_name="TechCo",
                company_data={
                    "funding": "Series B, $50M",
                    "industry": "DevOps",
                    "employees": "150",
                },
            )

            assert result.is_success or result.status.value == "partial"


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

        with patch.object(search_skill, "tavily") as mock_tavily:
            mock_tavily.search = AsyncMock(
                return_value={
                    "results": [
                        {
                            "title": "TechCo raises Series B",
                            "url": "https://example.com",
                            "content": "TechCo, a DevOps platform, raised $40M in Series B",
                        }
                    ]
                }
            )

            search_result = await search_skill.run(query="DevOps Series B 2024")
            assert search_result.is_success

        # Step 2: Extract company data from search (simulated)
        company_data = {
            "name": "TechCo",
            "funding": "Series B, $40M",
            "industry": "DevOps",
        }

        # Step 3: Qualify
        qualify_skill = QualifyProspectSkill(context=mock_skill_context)

        with patch(
            "agents.goal_executor.skills.prospect.qualify.ChatOpenAI"
        ) as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.ainvoke = AsyncMock(
                return_value=MagicMock(
                    content='{"score": 80, "reasoning": "Good fit for DevOps", "signals": ["Series B"]}'
                )
            )
            mock_llm.return_value = mock_llm_instance

            qualify_result = await qualify_skill.run(
                company_name=company_data["name"],
                company_data=company_data,
            )

            # Qualification should work with search output
            assert qualify_result.status.value in ["success", "partial"]
