import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from agents.company_profile import prompts
from agents.company_profile.utils import format_research_context
from agents.company_profile.tools.internal_search import internal_search_tool

# Load root-level .env so VECTOR_* and LLM keys are available
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


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

    # Check if AllCampus case study data exists in vector DB
    has_case_study_data = (
        "AllCampus - OPM Case Study" in result
        or "Partner Hub" in result
        or "Archa" in result
        or "case study" in result.lower()
    )

    if not has_case_study_data:
        pytest.skip(
            "AllCampus case study not found in vector DB - data needs to be ingested. "
            "Run: cd ingest && python main.py --folder-id <allcampus-case-study-folder>"
        )

    # Synthesis must explicitly declare relationship when case study data exists
    assert "Relationship status: Existing client" in result
    # Should reference project cues (case study filename or well-known project terms)
    assert (
        "AllCampus - OPM Case Study" in result
        or "Partner Hub" in result
        or "Archa" in result
    )

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
    # Project details should flow into the prompt
    assert (
        "AllCampus - OPM Case Study" in system_prompt
        or "Partner Hub" in system_prompt
        or "Archa" in system_prompt
    )
    assert "Relationship status: Existing client" in system_prompt
