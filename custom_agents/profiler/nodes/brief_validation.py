"""Research brief validation node for deep research workflow.

Uses LLM-as-a-judge to validate research brief quality before research begins.
Ensures briefs have sufficient depth, coverage, and focus alignment.
"""

import json
import logging
import re

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from agents.profiler.state import ProfileAgentState
from config.settings import Settings

logger = logging.getLogger(__name__)

# Validation prompt for LLM judge (COMPANY profiles)
BRIEF_VALIDATION_PROMPT = """You are validating a research brief for a company profile investigation.

<Research Brief to Evaluate>
{research_brief}
</Research Brief to Evaluate>

<Focus Area (if specified)>
{focus_area}
</Focus Area>

<Validation Criteria - Keep it Practical>

Your job is to check these 4 things:

1. **Question Count & Depth**
   - Does the brief have 15-30 specific investigative questions?
   - Are questions specific and investigative (not generic "tell me about...")?
   - Example GOOD: "What factors led to their recent pivot into AI infrastructure?"
   - Example BAD: "Tell me about their products"

2. **Section Coverage**
   - Does it cover the 9 core sections: History, Leadership, Products, Customers, Market Position, Company Priorities, Size of Teams, Tech Stack, Solutions?
   - At least 2-3 questions per major section?

3. **Focus Alignment** (if focus area was specified)
   - If user asked about a specific focus (e.g., "AI needs"), do 50-70% of questions relate to it?
   - Does the brief explicitly call out the focus area in "Research Priorities"?

4. **Research Priorities Section**
   - Is there a clear "Research Priorities" section identifying what's most important?
   - Does it explain WHY certain areas matter for BD?

**Don't nitpick minor formatting or wording - focus on whether this brief will produce USEFUL research.**

<Your Response Format>

Return ONLY a JSON object:

```json
{{
  "passes_validation": true/false,
  "issues": ["Issue 1", "Issue 2"],
  "question_count": 25,
  "has_research_priorities": true/false,
  "section_coverage": {{
    "covered_sections": 9,
    "missing_sections": []
  }},
  "focus_alignment": {{
    "focus_requested": "AI needs and capabilities" or "None",
    "relevant_question_ratio": 0.65,
    "alignment_adequate": true/false
  }},
  "revision_instructions": "Specific instructions if it fails (or empty string if passes)"
}}
```

**Examples:**

**Example 1: PASS - Good brief with focus**
```json
{{
  "passes_validation": true,
  "issues": [],
  "question_count": 28,
  "has_research_priorities": true,
  "section_coverage": {{
    "covered_sections": 9,
    "missing_sections": []
  }},
  "focus_alignment": {{
    "focus_requested": "DevOps needs",
    "relevant_question_ratio": 0.68,
    "alignment_adequate": true
  }},
  "revision_instructions": ""
}}
```

**Example 2: FAIL - Not enough questions**
```json
{{
  "passes_validation": false,
  "issues": ["Only 8 questions total - need at least 15 investigative questions"],
  "question_count": 8,
  "has_research_priorities": true,
  "section_coverage": {{
    "covered_sections": 9,
    "missing_sections": []
  }},
  "focus_alignment": {{
    "focus_requested": "None",
    "relevant_question_ratio": null,
    "alignment_adequate": null
  }},
  "revision_instructions": "Generate 15-25 specific investigative questions covering all 9 sections. Each major section should have 2-4 deep questions."
}}
```

**Example 3: FAIL - Focus misalignment**
```json
{{
  "passes_validation": false,
  "issues": ["User asked about AI needs but only 2 of 20 questions relate to AI/ML"],
  "question_count": 20,
  "has_research_priorities": true,
  "section_coverage": {{
    "covered_sections": 9,
    "missing_sections": []
  }},
  "focus_alignment": {{
    "focus_requested": "AI needs and capabilities",
    "relevant_question_ratio": 0.10,
    "alignment_adequate": false
  }},
  "revision_instructions": "Rewrite to focus on AI: In Company Priorities, ask about AI initiatives. In Size of Teams, investigate ML/AI team structure. In Tech Stack, explore AI/ML tools. In Solutions, propose AI consulting opportunities. Aim for 12-15 AI-related questions out of 20 total."
}}
```

Validate the brief and return JSON only.
"""

# Validation prompt for LLM judge (EMPLOYEE/PERSON profiles)
EMPLOYEE_BRIEF_VALIDATION_PROMPT = """You are validating a research brief for an individual/employee profile investigation.

<Research Brief to Evaluate>
{research_brief}
</Research Brief to Evaluate>

<Focus Area (if specified)>
{focus_area}
</Focus Area>

<Validation Criteria - Keep it Practical>

Your job is to check these 4 things:

1. **Question Count & Depth**
   - Does the brief have 15-30 specific investigative questions?
   - Are questions specific and investigative (not generic "tell me about...")?
   - Example GOOD: "What thought leadership has [Person] published on AI/ML topics?"
   - Example BAD: "Tell me about their background"

2. **Section Coverage for EMPLOYEE profiles**
   - Does it cover the 8 core sections: Professional Background & Career Path, Current Role & Responsibilities, Professional Expertise & Specializations, Public Presence & Thought Leadership, Current Company Context, Professional Interests & Priorities, Network & Relationships, Engagement Opportunities & Approach?
   - At least 2-3 questions per major section?

3. **Focus Alignment** (if focus area was specified)
   - If user asked about a specific focus, do 50-70% of questions relate to it?
   - Does the brief explicitly call out the focus area in "Research Priorities"?

4. **Research Priorities Section**
   - Is there a clear "Research Priorities" section identifying what's most important?
   - Does it explain WHY certain areas matter for BD/relationship building?

**Don't nitpick minor formatting or wording - focus on whether this brief will produce USEFUL research about this PERSON.**

<Your Response Format>

Return ONLY a JSON object:

```json
{{
  "passes_validation": true/false,
  "issues": ["Issue 1", "Issue 2"],
  "question_count": 25,
  "has_research_priorities": true/false,
  "section_coverage": {{
    "covered_sections": 8,
    "missing_sections": []
  }},
  "focus_alignment": {{
    "focus_requested": "AI expertise and interests" or "None",
    "relevant_question_ratio": 0.65,
    "alignment_adequate": true/false
  }},
  "revision_instructions": "Specific instructions if it fails (or empty string if passes)"
}}
```

Validate the brief and return JSON only.
"""


def count_questions_in_brief(brief: str) -> int:
    """Count question marks in research brief as proxy for question count.

    Args:
        brief: Research brief text

    Returns:
        Number of questions found

    """
    # Count lines ending with '?'
    lines = brief.split("\n")
    question_count = sum(1 for line in lines if line.strip().endswith("?"))
    return question_count


async def validate_research_brief(
    state: ProfileAgentState, config: RunnableConfig
) -> dict:
    """Validate research brief quality before starting research.

    Checks:
    - Sufficient question count (15-30)
    - Coverage of all 9 core sections
    - Focus area alignment (if specified)
    - Research priorities clearly identified

    Args:
        state: Current agent state with research_brief
        config: Runtime configuration

    Returns:
        Dict with brief_passes_validation, brief_revision_instructions

    """
    research_brief = state.get("research_brief", "")
    focus_area = state.get("focus_area", "")
    brief_revision_count = state.get("brief_revision_count", 0)
    profile_type = state.get("profile_type", "company")

    if focus_area:
        logger.info(
            f"Validating {profile_type} research brief (revision {brief_revision_count}) - Focus: {focus_area}"
        )
    else:
        logger.info(
            f"Validating {profile_type} research brief (revision {brief_revision_count})"
        )

    # Quick sanity check
    question_count = count_questions_in_brief(research_brief)
    logger.info(
        f"Brief stats: {len(research_brief)} chars, ~{question_count} questions"
    )

    # Initialize LLM judge
    try:
        settings = Settings()
        judge_llm = ChatOpenAI(
            model="gpt-4o",  # Use GPT-4o for accurate validation
            api_key=settings.llm.api_key,
            temperature=0.0,  # Deterministic evaluation
            max_completion_tokens=500,
        )

        # Select appropriate validation prompt based on profile type
        if profile_type == "employee":
            validation_prompt = EMPLOYEE_BRIEF_VALIDATION_PROMPT
        else:
            validation_prompt = BRIEF_VALIDATION_PROMPT

        # Run validation
        prompt = validation_prompt.format(
            research_brief=research_brief,
            focus_area=focus_area if focus_area else "None (general profile)",
        )
        response = await judge_llm.ainvoke(prompt)
        response_text = response.content.strip()

        logger.debug(f"Judge response: {response_text[:200]}...")

        # Parse JSON response
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            json_text = json_match.group(0) if json_match else response_text

        evaluation = json.loads(json_text)

        passes_validation = evaluation.get("passes_validation", False)
        issues = evaluation.get("issues", [])
        revision_instructions = evaluation.get("revision_instructions", "")

        # Extract details
        question_count_judge = evaluation.get("question_count", 0)
        has_research_priorities = evaluation.get("has_research_priorities", False)

        # Extract focus alignment with null safety
        focus_alignment = evaluation.get("focus_alignment") or {}
        alignment_adequate = focus_alignment.get("alignment_adequate")
        relevant_ratio = focus_alignment.get("relevant_question_ratio")

        if passes_validation:
            logger.info("✅ Research brief PASSED validation")
            logger.info(f"   Questions: {question_count_judge}")
            logger.info(f"   Research Priorities: {has_research_priorities}")
            if relevant_ratio is not None:
                logger.info(f"   Focus alignment: {relevant_ratio:.0%}")

            return {
                "brief_passes_validation": True,
                "brief_revision_instructions": None,
            }

        # Brief failed validation
        logger.warning(f"❌ Research brief FAILED validation: {len(issues)} issues")
        logger.warning(f"   Questions counted: {question_count_judge}")
        logger.warning(f"   Has priorities section: {has_research_priorities}")
        if alignment_adequate is not None:
            logger.warning(f"   Focus alignment adequate: {alignment_adequate}")
        for issue in issues:
            logger.warning(f"  - {issue}")

        # Check if we've exceeded max revisions
        if brief_revision_count >= 1:
            logger.error(
                "❌ Max brief revisions (1) exceeded, proceeding with imperfect brief"
            )
            # Add warning to brief
            warning_text = (
                "\n\n---\n\n"
                "⚠️ **Research Brief Warning**: This brief did not pass validation after 2 attempts (1 initial + 1 revision). "
                f"Known issues: {', '.join(issues)}\n\n"
            )
            updated_brief = research_brief + warning_text
            return {
                "brief_passes_validation": False,
                "brief_max_revisions_exceeded": True,
                "research_brief": updated_brief,
                "brief_revision_instructions": None,
            }

        # Request revision
        logger.info(f"🔄 Requesting brief revision {brief_revision_count + 1}/1")

        # Build revision prompt
        revision_prompt = f"""Your previous research brief did not pass validation. Please revise it to fix these issues:

{chr(10).join(f"{i + 1}. {issue}" for i, issue in enumerate(issues))}

**Specific Instructions:**
{revision_instructions}

Generate the complete revised research brief now.
"""

        return {
            "brief_passes_validation": False,
            "brief_max_revisions_exceeded": False,
            "brief_revision_count": brief_revision_count + 1,
            "brief_revision_prompt": revision_prompt,
        }

    except Exception as e:
        logger.error(f"Brief validation error: {e}", exc_info=True)
        # On error, proceed anyway (don't block the workflow)
        logger.warning("⚠️ Brief validation failed, proceeding with brief")
        return {
            "brief_passes_validation": True,  # Treat errors as pass
            "brief_revision_instructions": None,
        }


def research_brief_router(state: ProfileAgentState) -> str:
    """Route research brief validation results.

    This function is used by add_conditional_edges to determine the next node.
    It makes the brief validation loop visible in LangGraph Studio.

    Args:
        state: Current agent state with validation results

    Returns:
        "proceed" to continue to research_supervisor, or "revise" to loop back

    """
    brief_passes = state.get("brief_passes_validation", False)
    max_revisions = state.get("brief_max_revisions_exceeded", False)

    if brief_passes:
        logger.info("✅ Router: Brief validation passed, proceeding to research")
        return "proceed"

    if max_revisions:
        logger.warning(
            "⚠️ Router: Max brief revisions exceeded, proceeding to research anyway"
        )
        return "proceed"

    # Validation failed and revisions available - loop back
    logger.info(
        "🔄 Router: Brief validation failed, looping back to write_research_brief"
    )
    return "revise"
