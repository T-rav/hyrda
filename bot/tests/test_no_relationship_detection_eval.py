import re

import pytest

from agents.company_profile import prompts
from agents.company_profile.utils import format_research_context


@pytest.mark.asyncio
async def test_internal_kb_no_relationship_for_3m():
    """
    Simulate internal_search_tool output for 'profile 3M and their ai needs'
    where internal docs contain only research notes (no project/engagement cues).

    Verify that:
    - Relationship status is reported as "No prior engagement"
    - Internal KB sources are present in the formatted context
    - Final report prompt includes the internal evidence without inferring a client relationship
    """

    internal_search_note = (
        "# Internal Knowledge Base Search\n\n"
        "Relationship status: No prior engagement\n\n"
        "Internal 8th Light knowledge base analysis indicates prior research has been conducted on 3M,\n"
        "focusing on AI initiatives and public technology posture. This does not indicate any formal\n"
        "client engagement, proposals, or delivered project work.\n\n"
        "**Found in 1 internal document (1 section):**\n"
        "- 3M Research Notes (relevance: 84%)\n\n"
        "**Search Strategy:** 3 focused queries (retrieved 3 total sections)\n\n"
        "### Sources\n\n"
        "1. internal://knowledge-base - Internal search result: 3M Research Notes\n"
    )

    context = await _format_context_safely(
        research_brief="Focus AI needs and internal relationships",
        notes=[internal_search_note],
        profile_type="company",
    )

    # Context should include internal KB source and explicitly state no prior engagement
    assert "Internal search result:" in context
    assert "Relationship status: No prior engagement" in context
    assert "Existing client/past engagement" not in context

    # Build final system prompt
    system_prompt = prompts.final_report_generation_prompt.format(
        profile_type="company",
        focus_area="AI needs",
        focus_guidance="",
        notes=context,
        current_date="October 15, 2025",
    )

    # Prompt should carry the internal evidence and not assert client relationship
    assert "## Relationships via 8th Light Network" in system_prompt
    assert "Internal search result:" in system_prompt
    assert "Relationship status: No prior engagement" in system_prompt
    assert "Existing client/past engagement" not in system_prompt


async def _format_context_safely(
    research_brief: str, notes: list[str], profile_type: str
) -> str:
    formatted = await format_research_context(
        research_brief, notes, profile_type, max_sources=25
    )
    return _strip_excess_whitespace(re.sub(r"\s+\n", "\n", formatted))


def _strip_excess_whitespace(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()
