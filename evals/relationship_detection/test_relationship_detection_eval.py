import re

import pytest
from agents.profiler import prompts
from agents.profiler.utils import format_research_context


@pytest.mark.asyncio
async def test_internal_kb_relationship_detection_context_and_prompt():
    """
    Simulate internal_search_tool output for 'profile allcampus and their ai needs'
    and verify that:
    - Relationship status from internal notes is present (Existing client/past engagement)
    - Internal KB sources are present in the formatted research context
    - Final report system prompt includes the Relationships guidance and the internal notes
    """

    # Simulated internal search result with numbered sources and explicit relationship
    internal_search_note = (
        "# Internal Knowledge Base Search\n\n"
        "Relationship status: Existing client/past engagement\n\n"
        "Evidence from internal documents indicates completed project work for AllCampus, including:\n"
        "- Partner Hub application build (customer/partner management)\n"
        "- Archa platform facelift (design and technology strategy)\n"
        "- AWS infrastructure with Terraform as IaC\n\n"
        "**Found in 1 internal document (multiple sections):**\n"
        "- AllCampus - OPM Case Study (relevance: 98%)\n\n"
        "**Search Strategy:** 3 focused queries (retrieved 7 total sections)\n\n"
        "### Sources\n\n"
        "1. https://docs.google.com/document/d/1ZJYTdGOPABTGjKEaktozZwoz2Z7_hHh1DMRADcvOa44/edit?usp=drivesdk - Internal search result: AllCampus - OPM Case Study\n"
    )

    # Format context without pruning (keep <=25 sources)
    context = await _format_context_safely(
        research_brief="Focus AI needs and internal relationships",
        notes=[internal_search_note],
        profile_type="company",
    )

    # Assert internal KB sources are present
    assert "Internal search result:" in context

    # Assert relationship status line is preserved in findings
    assert "Relationship status: Existing client/past engagement" in context

    # Build final system prompt with the context embedded as notes
    system_prompt = prompts.final_report_generation_prompt.format(
        profile_type="company",
        focus_area="AI needs",
        focus_guidance="",
        notes=context,
        current_date="October 15, 2025",
    )

    # Ensure Relationships section guidance is present in the prompt
    assert "## Relationships via 8th Light Network" in system_prompt
    assert "CHECK FOR INTERNAL SEARCH RESULTS FIRST" in system_prompt

    # The system prompt should carry the internal notes (so the model can see relationship evidence)
    assert "Internal search result:" in system_prompt
    assert "AllCampus - OPM Case Study" in system_prompt


async def _format_context_safely(
    research_brief: str, notes: list[str], profile_type: str
) -> str:
    """Helper that calls format_research_context while avoiding the LLM pruning path."""
    # The pruning branch only triggers if sources > max_sources; keep it small to avoid LLM calls
    # Also sanitize to ensure our test is deterministic
    # Note: The function itself does not depend on external services in the non-pruning path
    formatted = await format_research_context(
        research_brief, notes, profile_type, max_sources=25
    )
    return _strip_excess_whitespace(re.sub(r"\s+\n", "\n", formatted))


def _strip_excess_whitespace(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()
