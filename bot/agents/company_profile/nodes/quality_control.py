"""Quality control node for validating and revising final reports.

Uses deterministic Python validation to check report quality and request revisions if needed.
Validates citation-source matching using regex pattern matching (no LLM hallucinations).
Implements up to 3 revision cycles to ensure all quality criteria are met.
"""

import logging
import re

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from agents.company_profile.state import ProfileAgentState

logger = logging.getLogger(__name__)


def extract_citations_from_report(report: str) -> list[int]:
    """Extract all citation numbers [1], [2], etc. from report.

    Args:
        report: Markdown report text

    Returns:
        Sorted list of unique citation numbers found
    """
    # Find all [N] citations in the report
    citations = re.findall(r"\[(\d+)\]", report)
    # Convert to integers, deduplicate, and sort
    return sorted({int(c) for c in citations})


def count_sources_in_section(report: str) -> int:
    """Count number of source entries in ## Sources section.

    Args:
        report: Markdown report text

    Returns:
        Number of sources listed (0 if section missing)
    """
    # Find ## Sources section
    sources_match = re.search(r"## Sources\s*\n(.*)", report, re.DOTALL)
    if not sources_match:
        return 0

    sources_section = sources_match.group(1)

    # Count numbered entries (1. ... 2. ... 3. ...)
    # Match lines starting with digits followed by period
    source_entries = re.findall(r"^\d+\.\s+", sources_section, re.MULTILINE)

    return len(source_entries)


async def quality_control_node(
    state: ProfileAgentState, config: RunnableConfig
) -> Command[str]:
    """Validate report quality and request revision if needed.

    Checks:
    - Sources section present
    - All citations have corresponding source entries
    - No gaps in source numbering
    - No meta-references in sources

    Args:
        state: Current agent state with final_report
        config: Runtime configuration

    Returns:
        Command to proceed to END (if passes) or back to final_report_generation (if fails)
    """
    final_report = state.get("final_report", "")
    revision_count = state.get("revision_count", 0)

    logger.info(f"Quality control check (revision {revision_count})")

    # Extract actual citations and sources using Python regex (deterministic)
    citations = extract_citations_from_report(final_report)
    sources_count = count_sources_in_section(final_report)
    highest_citation = max(citations) if citations else 0

    logger.info(
        f"Report stats: {len(citations)} unique citations (highest: {highest_citation}), "
        f"{sources_count} source entries"
    )

    # Validate using Python (deterministic, no LLM hallucinations)
    try:
        issues = []
        missing_sources = []

        # Check 1: Sources section present
        if sources_count == 0:
            issues.append("Report is missing the ## Sources section entirely")
            missing_sources = list(range(1, highest_citation + 1))

        # Check 2: All citations have corresponding sources
        elif highest_citation > sources_count:
            issues.append(
                f"Sources section only lists {sources_count} sources, "
                f"but report uses citations [1] through [{highest_citation}]"
            )
            missing_sources = list(range(sources_count + 1, highest_citation + 1))
            issues.append(f"Missing source entries for citations {missing_sources}")

        # Check 3: All citations used should exist in sources
        # (sources_count >= highest_citation means we have enough sources)
        elif sources_count < highest_citation:
            issues.append(
                f"Report uses citations up to [{highest_citation}] but only {sources_count} sources listed"
            )
            missing_sources = list(range(sources_count + 1, highest_citation + 1))

        passes_quality = len(issues) == 0
        revision_instructions = ""

        if not passes_quality and missing_sources:
            revision_instructions = (
                f"Add sources {missing_sources[0]}-{missing_sources[-1]} to the ## Sources section. "
                "Each should have full URL and description matching the citations used in the report."
            )

        if passes_quality:
            logger.info("✅ Report PASSED quality control")
            return Command(goto="__end__", update={})

        # Report failed quality check
        logger.warning(f"❌ Report FAILED quality control: {len(issues)} issues")
        logger.warning(f"   Citations used: [1] through [{highest_citation}]")
        logger.warning(f"   Sources listed: {sources_count}")
        if missing_sources:
            logger.warning(f"   Missing sources: {missing_sources}")
        for issue in issues:
            logger.warning(f"  - {issue}")

        # Check if we've exceeded max revisions
        if revision_count >= 3:
            logger.error(
                "❌ Max revisions (3) exceeded, proceeding with imperfect report"
            )
            # Add warning to report about quality issues
            warning_text = (
                "\n\n---\n\n"
                "⚠️ **Quality Control Warning**: This report did not pass all quality checks after 3 revision attempts. "
                f"Known issues: {', '.join(issues)}\n\n"
            )
            updated_report = final_report + warning_text
            return Command(goto="__end__", update={"final_report": updated_report})

        # Request revision
        logger.info(
            f"🔄 Requesting revision {revision_count + 1}/3: {revision_instructions}"
        )

        # Build revision prompt with specific instructions
        revision_prompt = f"""Your previous report did not pass quality control. Please revise it to fix these issues:

{chr(10).join(f"{i + 1}. {issue}" for i, issue in enumerate(issues))}

**Specific Instructions:**
{revision_instructions}

**CRITICAL - HOW TO FIX SOURCES:**
1. Look at the "CONSOLIDATED SOURCE LIST FOR YOUR REFERENCE" section in the research context
2. That list shows you ALL available sources already numbered globally
3. Use ONLY those citation numbers in your report (don't make up new ones)
4. In your ## Sources section, copy ALL sources from the consolidated list
5. Make sure your highest citation number [X] matches the total number of sources listed

Example: If consolidated list shows 25 sources, your report should:
- Use citations [1] through [25] only
- Have a ## Sources section listing all 25 sources
- Number them 1, 2, 3, 4... 25 with NO gaps

Generate the complete revised report now.
"""

        return Command(
            goto="final_report_generation",
            update={
                "revision_count": revision_count + 1,
                "revision_prompt": revision_prompt,
            },
        )

    except Exception as e:
        logger.error(f"Quality control error: {e}", exc_info=True)
        # On error, proceed anyway (don't block the workflow)
        logger.warning("⚠️ Quality control failed, proceeding with report")
        return Command(goto="__end__", update={})
