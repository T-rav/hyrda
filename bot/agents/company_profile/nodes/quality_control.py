"""Quality control node for validating and revising final reports.

Uses LLM-as-a-judge to validate report quality and request revisions if needed.
Implements up to 3 revision cycles to ensure all quality criteria are met.
"""

import logging
import re

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.types import Command

from agents.company_profile.state import ProfileAgentState
from config.settings import Settings

logger = logging.getLogger(__name__)

# Quality validation prompt for LLM judge
QUALITY_JUDGE_PROMPT = """You are a quality control inspector doing a HIGH-LEVEL check of a company profile report.

<Report to Evaluate>
{report}
</Report to Evaluate>

<Focus Area (if specified)>
{focus_area}
</Focus Area>

<Quality Inspection - Keep it Simple>

Your job is to do a QUICK INSPECTION for these 2 critical things:

1. **Sources Are Present**
   - Does the report have a "## Sources" section?
   - Are there at least 5-10 source entries listed?
   - (Don't worry about exact citation matching - just verify sources exist)

2. **Alignment to User's Goal** (if focus area was specified)
   - If a specific focus area was requested (e.g., "AI needs"), does the report actually address it?
   - Are the relevant sections (Company Priorities, Size of Teams, Solutions) detailed about the focus?
   - Or did the report ignore the user's specific question?

**That's it. Don't nitpick formatting, structure, writing style, or citation numbering.**

<Your Response Format>

Return ONLY a JSON object:

```json
{{
  "passes_quality": true/false,
  "issues": ["Issue 1", "Issue 2"],
  "sources_check": {{
    "has_sources_section": true/false,
    "sources_count": 12,
    "has_adequate_sources": true/false
  }},
  "focus_alignment_check": {{
    "focus_area_requested": "AI needs and capabilities" or "None",
    "report_addresses_focus": true/false/null,
    "alignment_notes": "Brief note on whether report covers the focus area adequately"
  }},
  "revision_instructions": "Simple instructions if it fails (or empty string if passes)"
}}
```

**Examples:**

**Example 1: PASS - Good sources, good alignment**
```json
{{
  "passes_quality": true,
  "issues": [],
  "sources_check": {{
    "has_sources_section": true,
    "sources_count": 12,
    "has_adequate_sources": true
  }},
  "focus_alignment_check": {{
    "focus_area_requested": "AI needs and capabilities",
    "report_addresses_focus": true,
    "alignment_notes": "Company Priorities and Size of Teams sections both extensively cover AI initiatives and ML team structure"
  }},
  "revision_instructions": ""
}}
```

**Example 2: FAIL - No sources section**
```json
{{
  "passes_quality": false,
  "issues": ["Report is missing the ## Sources section"],
  "sources_check": {{
    "has_sources_section": false,
    "sources_count": 0,
    "has_adequate_sources": false
  }},
  "focus_alignment_check": {{
    "focus_area_requested": "None",
    "report_addresses_focus": null,
    "alignment_notes": "No specific focus requested"
  }},
  "revision_instructions": "Add a ## Sources section at the end with at least 10 source URLs/references"
}}
```

**Example 3: FAIL - Doesn't address focus**
```json
{{
  "passes_quality": false,
  "issues": ["Report doesn't adequately address the user's specific focus on DevOps needs"],
  "sources_check": {{
    "has_sources_section": true,
    "sources_count": 15,
    "has_adequate_sources": true
  }},
  "focus_alignment_check": {{
    "focus_area_requested": "DevOps practices and infrastructure",
    "report_addresses_focus": false,
    "alignment_notes": "User asked about DevOps but Company Priorities and Size of Teams barely mention DevOps, CI/CD, or infrastructure. Solutions section doesn't propose DevOps consulting opportunities."
  }},
  "revision_instructions": "Rewrite to emphasize DevOps throughout. In Company Priorities, highlight infrastructure initiatives. In Size of Teams, analyze DevOps/SRE team. In Solutions, propose DevOps transformation opportunities."
}}
```

Do a quick inspection and return JSON only. Don't overthink it.
"""


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
    focus_area = state.get("focus_area", "")

    if focus_area:
        logger.info(
            f"Quality control check (revision {revision_count}) - Focus: {focus_area}"
        )
    else:
        logger.info(f"Quality control check (revision {revision_count})")

    # Extract actual citations and sources for logging
    citations = extract_citations_from_report(final_report)
    sources_count = count_sources_in_section(final_report)

    logger.info(
        f"Report stats: {len(citations)} unique citations (highest: {max(citations) if citations else 0}), "
        f"{sources_count} source entries"
    )

    # Initialize LLM judge
    try:
        settings = Settings()
        judge_llm = ChatOpenAI(
            model="gpt-4o",  # Use GPT-4o for accurate validation (no hallucinations)
            api_key=settings.llm.api_key,
            temperature=0.0,  # Deterministic evaluation
            max_completion_tokens=500,
        )

        # Run quality evaluation
        prompt = QUALITY_JUDGE_PROMPT.format(
            report=final_report,
            focus_area=focus_area if focus_area else "None (general profile)",
        )
        response = await judge_llm.ainvoke(prompt)
        response_text = response.content.strip()

        logger.debug(f"Judge response: {response_text[:200]}...")

        # Parse JSON response
        import json

        # Extract JSON from markdown code blocks if present
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            json_text = json_match.group(0) if json_match else response_text

        evaluation = json.loads(json_text)

        passes_quality = evaluation.get("passes_quality", False)
        issues = evaluation.get("issues", [])
        revision_instructions = evaluation.get("revision_instructions", "")

        # Extract sources check details with null safety
        sources_check = evaluation.get("sources_check") or {}
        sources_count_judge = sources_check.get("sources_count", 0)
        has_adequate_sources = sources_check.get("has_adequate_sources", False)

        # Extract focus alignment check details with null safety
        focus_alignment = evaluation.get("focus_alignment_check") or {}
        alignment_notes = focus_alignment.get("alignment_notes", "")

        if passes_quality:
            logger.info("✅ Report PASSED quality control")
            logger.info(
                f"   Sources: {sources_count_judge} entries (adequate: {has_adequate_sources})"
            )
            if alignment_notes:
                logger.info(f"   Focus alignment: {alignment_notes}")
            # IMPORTANT: Return the state so LangGraph includes it in the final event
            # Without this, Command(goto="__end__", update={}) causes LangGraph to send None
            return Command(goto="__end__", update=state)

        # Report failed quality check
        logger.warning(f"❌ Report FAILED quality control: {len(issues)} issues")
        logger.warning(
            f"   Sources listed: {sources_count_judge} (adequate: {has_adequate_sources})"
        )
        if alignment_notes:
            logger.warning(f"   Focus alignment: {alignment_notes}")
        for issue in issues:
            logger.warning(f"  - {issue}")

        # Check if we've exceeded max revisions
        # revision_count 0 = initial attempt, 1 = 1st revision (max)
        if revision_count >= 1:
            logger.error(
                "❌ Max revisions (1) exceeded, proceeding with imperfect report"
            )
            # Add warning to report about quality issues
            warning_text = (
                "\n\n---\n\n"
                "⚠️ **Quality Control Warning**: This report did not pass all quality checks after 2 attempts (1 initial + 1 revision). "
                f"Known issues: {', '.join(issues)}\n\n"
            )
            updated_report = final_report + warning_text
            return Command(goto="__end__", update={"final_report": updated_report})

        # Request revision
        logger.info(
            f"🔄 Requesting revision {revision_count + 1}/1: {revision_instructions}"
        )

        # Build revision prompt with specific instructions
        revision_prompt = f"""Your previous report did not pass quality control. Please revise it to fix these issues:

{chr(10).join(f"{i + 1}. {issue}" for i, issue in enumerate(issues))}

**Specific Instructions:**
{revision_instructions}

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
        return Command(goto="__end__", update=state)
