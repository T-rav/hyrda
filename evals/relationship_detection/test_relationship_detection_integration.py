import os

import pytest

from agents.company_profile import prompts
from agents.company_profile.utils import format_research_context
from agents.company_profile.tools.internal_search import internal_search_tool


@pytest.mark.asyncio
@pytest.mark.integration
async def test_allcampus_relationship_integration_real_services():
    """
    End-to-end style check that uses real Qdrant + LLM if configured.

    Query: 'profile allcampus and their ai needs'
    Expectation: Internal search returns AllCampus case study evidence and synthesis
    sets explicit relationship status as existing/past engagement.
    """

    # Require env for real integration; otherwise skip
    if not os.getenv("VECTOR_HOST"):
        pytest.skip("VECTOR_HOST not configured - skipping integration test")
    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        pytest.skip("LLM API key not configured - skipping integration test")

    tool = internal_search_tool()
    if tool is None or getattr(tool, "vector_store", None) is None:
        pytest.skip("Internal search tool not available - skipping integration test")
    if getattr(tool, "llm", None) is None:
        pytest.skip(
            "LLM not available for internal_search_tool - skipping integration test"
        )

    # Run the real internal search
    result = await tool._arun("profile allcampus and their ai needs", effort="medium")

    # Should reference the real AllCampus internal case study doc name
    assert "AllCampus - OPM Case Study" in result
    # Synthesis must explicitly declare relationship
    assert "Relationship status: Existing client" in result

    # Build context and system prompt to ensure the evidence flows into report generation
    context = await format_research_context(
        research_brief="Focus AI needs and internal relationships",
        notes=[result],
        profile_type="company",
        max_sources=25,
    )

    assert "Internal search result:" in context

    system_prompt = prompts.final_report_generation_prompt.format(
        profile_type="company",
        focus_area="AI needs",
        focus_guidance="",
        notes=context,
        current_date="October 15, 2025",
    )

    assert "## Relationships via 8th Light Network" in system_prompt
    assert "Internal search result:" in system_prompt
    assert "AllCampus - OPM Case Study" in system_prompt
    assert "Relationship status: Existing client" in system_prompt
