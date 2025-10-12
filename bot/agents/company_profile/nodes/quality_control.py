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
QUALITY_JUDGE_PROMPT = """You are a quality control judge evaluating a company profile report.

<Report to Evaluate>
{report}
</Report to Evaluate>

<Quality Criteria - ALL MUST PASS>

1. **Sources Section Present**: Report MUST end with "## Sources" section
2. **All Citations Listed**: Sources section must list entries 1, 2, 3... up to the HIGHEST citation number used
3. **No Gaps in Numbering**: Sources must be numbered sequentially (1, 2, 3, 4...) with NO gaps
4. **External Sources Only**: No meta-references like "Internal research" or "Research findings" in Sources
5. **Complete Structure**: All required sections present (Overview, Priorities, News, Executive Team, etc.)

<Your Task>

**CRITICAL RULE**: The report may use citations out of order (e.g., [1], [5], [10]). That's OK!
What matters is: If the HIGHEST citation is [10], then the ## Sources section MUST list sources 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 (all of them, sequentially, no gaps).

**If you claim sources are missing, you MUST provide evidence by quoting the actual citation numbers you found and the source entries you counted.**

Step-by-step evaluation process:
1. Find the ## Sources section
2. Count the numbered source entries (1. 2. 3. etc.) - count ALL entries
3. Scan the report for ALL citations [1], [2], [3]... and note the HIGHEST number (not which ones are used!)
4. Compare: Does the sources count match the highest citation number?
5. If NO match, provide EXACT EVIDENCE of what you found

**EXAMPLE OF CORRECT EVALUATION**:
- Report uses citations: [1], [5], [10] (out of order - that's fine!)
- Highest citation: 10
- Sources section has: 1. 2. 3. 4. 5. 6. 7. 8. 9. 10. (10 entries)
- **RESULT: PASS** ✅ (all sources 1-10 are present, even though only [1], [5], [10] were cited)

Return ONLY a JSON object:

```json
{{
  "passes_quality": true/false,
  "issues": [
    "Description of issue 1 (if any)",
    "Description of issue 2 (if any)"
  ],
  "highest_citation": 15,
  "sources_count": 10,
  "missing_sources": [11, 12, 13, 14, 15],
  "evidence": "I found citations [1] through [18] in the report body. In the ## Sources section, I counted entries: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10. Therefore sources 11-18 are missing.",
  "revision_instructions": "Specific instructions for fixing issues (if fails)"
}}
```

**IMPORTANT**: The "evidence" field is REQUIRED when passes_quality is false. Show your work!

**Examples:**

**Example 1: PASS**
Report uses citations [1] through [12], Sources section lists 1-12 sequentially.
```json
{{
  "passes_quality": true,
  "issues": [],
  "highest_citation": 12,
  "sources_count": 12,
  "missing_sources": [],
  "evidence": "All citations [1]-[12] have corresponding source entries 1-12 in the ## Sources section.",
  "revision_instructions": ""
}}
```

**Example 2: FAIL - Missing Sources**
Report uses citations [1] through [18], but Sources section only lists 1-10.
```json
{{
  "passes_quality": false,
  "issues": [
    "Sources section only lists 10 sources, but report uses citations [1] through [18]",
    "Missing source entries for citations [11], [12], [13], [14], [15], [16], [17], [18]"
  ],
  "highest_citation": 18,
  "sources_count": 10,
  "missing_sources": [11, 12, 13, 14, 15, 16, 17, 18],
  "evidence": "Found citations [1], [2], [3]... up to [18] in the report. Counted source entries in ## Sources: 1. 2. 3. 4. 5. 6. 7. 8. 9. 10. Missing: 11-18.",
  "revision_instructions": "Add sources 11-18 to the ## Sources section. Each should have full URL and description matching the citations used in the report."
}}
```

**Example 3: FAIL - No Sources Section**
Report has no ## Sources section at all.
```json
{{
  "passes_quality": false,
  "issues": [
    "Report is missing the ## Sources section entirely",
    "Cannot verify citation coverage without Sources section"
  ],
  "highest_citation": 20,
  "sources_count": 0,
  "missing_sources": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
  "evidence": "Scanned entire report - no ## Sources section found. Found citations up to [20].",
  "revision_instructions": "Add a complete ## Sources section at the end of the report listing all 20 sources corresponding to citations [1] through [20] used in the report."
}}
```

**Example 4: PASS - Out of Order Citations**
Report uses citations [1], [5], [10] (out of order), Sources section lists 1-10.
```json
{{
  "passes_quality": true,
  "issues": [],
  "highest_citation": 10,
  "sources_count": 10,
  "missing_sources": [],
  "evidence": "Report uses citations [1], [5], [10]. Highest citation is [10]. Counted sources: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 (10 entries). All sources 1-10 are present - PASS.",
  "revision_instructions": ""
}}
```

Evaluate the report now and return JSON only.
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
        prompt = QUALITY_JUDGE_PROMPT.format(report=final_report)
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
        highest_citation = evaluation.get("highest_citation", 0)
        sources_count_judge = evaluation.get("sources_count", 0)
        missing_sources = evaluation.get("missing_sources", [])
        evidence = evaluation.get("evidence", "No evidence provided")

        if passes_quality:
            logger.info("✅ Report PASSED quality control")
            logger.info(f"   Evidence: {evidence}")
            return Command(goto="__end__", update={})

        # Report failed quality check
        logger.warning(f"❌ Report FAILED quality control: {len(issues)} issues")
        logger.warning(f"   Citations used: [1] through [{highest_citation}]")
        logger.warning(f"   Sources listed: {sources_count_judge}")
        if missing_sources:
            logger.warning(f"   Missing sources: {missing_sources}")
        logger.warning(f"   Evidence: {evidence}")
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
