"""Check if input has enough information for analysis.

This node determines if the sales notes contain sufficient information
to warrant a full MEDDPICC analysis, or if clarifying questions should
be asked first.

Uses LLM to intelligently assess information completeness rather than
rigid heuristics.
"""

import logging
import re

from langchain_openai import ChatOpenAI
from langgraph.graph.state import RunnableConfig

from agents.meddpicc_coach.state import MeddpiccAgentState
from config.settings import LLMSettings

logger = logging.getLogger(__name__)


async def check_input_completeness(
    state: MeddpiccAgentState, config: RunnableConfig
) -> dict[str, str | bool]:
    """Check if input has enough information for meaningful analysis.

    Uses LLM to intelligently assess if the sales notes contain sufficient
    information for a MEDDPICC analysis.

    Args:
        state: Current MEDDPICC agent state
        config: Runtime configuration

    Returns:
        Dict with needs_clarification flag and optional clarification message

    """
    query = state["query"]  # type: ignore[typeddict-item]

    logger.info(f"Checking input completeness ({len(query)} chars)")

    # Quick bypass for obviously too short input
    if len(query.strip()) < 20:
        logger.info("Input too short - needs clarification")
        clarification_msg = await _generate_clarification_message(query)
        return {
            "needs_clarification": True,
            "clarification_message": clarification_msg,
        }

    # Use LLM with structured output to guarantee JSON
    from pydantic import BaseModel, Field

    class InputAssessment(BaseModel):
        """Assessment of input completeness for MEDDPICC analysis."""

        decision: str = Field(
            description='Either "PROCEED" or "CLARIFY" based on information completeness'
        )
        reasoning: str = Field(
            description="Brief explanation of your decision (1-2 sentences)"
        )
        elements_found: list[str] = Field(
            description="List of MEDDPICC elements detected in the notes"
        )

    llm_settings = LLMSettings()  # type: ignore[call-arg]
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=llm_settings.api_key.get_secret_value(),
        temperature=0.0,
        max_completion_tokens=300,
    )

    # Use structured output to guarantee JSON
    structured_llm = llm.with_structured_output(InputAssessment)

    assessment_prompt = f"""You are assessing if sales call notes have enough information for a MEDDPICC analysis.

**YOUR ROLE**: Be EXTREMELY permissive. The goal is to help salespeople, not block them with nitpicking.

Sales notes:
\"\"\"{query}\"\"\"

**IMPORTANT**: If the notes contain "**Additional information:**", this is a multi-turn conversation where the user provided more details. You MUST evaluate the COMPLETE COMBINED context from ALL turns, not individual messages. The accumulated context as a whole may be sufficient even if the first message was vague.

MEDDPICC elements (PARTIAL information counts!):
- Metrics: ANY mention of improvements, savings, goals (doesn't need exact numbers)
- Economic Buyer: ANY mention of decision makers, budget holders, executives
- Decision Criteria: ANY hint about evaluation process
- Decision Process: ANY steps mentioned (even "need approval")
- Paper Process: Legal/procurement (often absent in early deals - THAT'S OK)
- Identify Pain: Business problems, frustrations, inefficiencies
- Champion: Person advocating internally (often the contact person)
- Competition: Alternatives considered (often absent - THAT'S OK)

**YOUR DECISION LOGIC - SIMPLE:**

If notes look like REAL CALL NOTES (any substance, details, context) → PROCEED
If notes are vague one-liners with zero context → CLARIFY

**PROCEED if ANY of these:**
- Has customer/company name + business context
- More than 100 words about a sales situation
- Multiple pain points or problems mentioned
- Structured format (sections, attendees, dates, etc.)
- Any call summary with details

**CLARIFY only if ALL of these:**
- Under 50 characters OR completely vague
- No customer/company name
- Zero specific business context

**EXAMPLES:**

PROCEED:
- "Jane's Equipment wants AI for scheduling" ✅
- Any structured call notes with company name ✅
- Multiple paragraphs about a deal ✅
- Pain points + customer name ✅

CLARIFY:
- "bob wants software" ❌ (too vague, no company)
- "help with deal" ❌ (zero context)
- "they need better reporting" ❌ (no customer name)

**DEFAULT: When in doubt → PROCEED**. Real call notes should always proceed, even if incomplete."""

    try:
        # Get structured output - guaranteed to be valid JSON matching schema
        assessment = await structured_llm.ainvoke(assessment_prompt)
        decision = assessment.decision.upper()
        reasoning = assessment.reasoning
        elements_found = assessment.elements_found

        logger.info(
            f"LLM assessment - Decision: {decision}, Elements: {elements_found}, Reasoning: {reasoning}"
        )

        if decision == "PROCEED":
            logger.info("✅ Proceeding with MEDDPICC analysis")
            return {"needs_clarification": False}
        else:
            logger.info("❓ Requesting clarification from user")
            clarification_msg = await _generate_clarification_message(query)
            return {
                "needs_clarification": True,
                "clarification_message": clarification_msg,
            }

    except Exception as e:
        logger.warning(f"LLM assessment failed: {e}, defaulting to PROCEED")
        # Default to proceeding if LLM fails (better UX than blocking)
        return {"needs_clarification": False}


async def _generate_clarification_message(query: str) -> str:
    """Generate a context-aware message asking for specific missing information.

    Uses LLM to intelligently identify what information is missing from the
    query and ask ONLY for those specific details.

    Args:
        query: Original query with partial information

    Returns:
        Dynamic clarification message with targeted questions

    """
    from pydantic import BaseModel, Field

    class ClarificationRequest(BaseModel):
        """What specific information we need from the user."""

        entity_name: str = Field(
            description="Company or person name extracted from notes (or 'this opportunity' if unclear)"
        )
        missing_elements: list[str] = Field(
            description="List of specific MEDDPICC elements that are unclear or missing"
        )
        specific_questions: list[str] = Field(
            description="3-5 specific, targeted follow-up questions based on what's already mentioned"
        )

    llm_settings = LLMSettings()  # type: ignore[call-arg]
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=llm_settings.api_key.get_secret_value(),
        temperature=0.3,  # Slightly higher for natural question generation
        max_completion_tokens=400,
    )

    structured_llm = llm.with_structured_output(ClarificationRequest)

    clarification_prompt = f"""You are helping a salesperson with MEDDPICC analysis. They've shared these notes:

\"\"\"{query}\"\"\"

MEDDPICC framework:
- Metrics: Quantifiable value/ROI
- Economic Buyer: Who has budget/authority?
- Decision Criteria: How they evaluate solutions
- Decision Process: Steps to get approval
- Paper Process: Legal/procurement steps
- Identify Pain: Business problems
- Champion: Internal advocate
- Competition: Alternatives they're considering

Analyze what information IS present and what's MISSING. Generate 3-5 SPECIFIC follow-up questions that:
1. Build on information they ALREADY mentioned (don't repeat what they told you)
2. Ask for the MOST CRITICAL missing pieces
3. Are conversational and natural (not a checklist)
4. Reference their specific context

Example (if they said "Bob wants a POS system"):
- "What problems is Bob trying to solve with the new POS? What's broken about their current setup?"
- "Who besides Bob will be involved in this decision? Who signs off on budget?"
- "Did Bob mention a timeline or urgency for making this change?"

Example (if they said "Acme Corp needs better reporting in Power BI"):
- "What specific metrics or KPIs are they struggling to track right now?"
- "How are they currently handling reporting, and why isn't it working?"
- "Who will be evaluating solutions - is it just the analytics team, or does IT/Finance get involved?"

Generate questions that feel like a helpful coach, not a form to fill out."""

    try:
        clarification = await structured_llm.ainvoke(clarification_prompt)

        entity_context = clarification.entity_name
        questions_list = "\n".join([f"- {q}" for q in clarification.specific_questions])

        return f"""Hey! I'd love to help you with the MEDDPICC analysis for {entity_context}, but I need a bit more context to give you solid coaching. 🎯

{questions_list}

The more details you provide, the better I can coach you on closing this deal! Feel free to paste raw notes or bullet points. 📝"""

    except Exception as e:
        logger.warning(f"Failed to generate dynamic clarification: {e}, using fallback")

        # Fallback to generic message
        name_match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", query)
        company_match = re.search(
            r"\b(from|at)\s+([A-Z][^\s]+(?:\s+[A-Z][^\s]+)*)", query
        )

        entity = None
        if company_match:
            entity = company_match.group(2)
        elif name_match:
            entity = name_match.group(1)

        context = f"your conversation with {entity}" if entity else "this opportunity"

        return f"""Hey! I'd love to help you with the MEDDPICC analysis for {context}, but I need a bit more context to give you solid coaching. 🎯

Can you share more about the call? For example:
- **What specific problems or pain points came up?** (e.g., "They're frustrated with 2-week deployment times")
- **Any numbers or metrics mentioned?** (e.g., "$200K budget", "50-person team", "need 3x faster")
- **Who did you talk to, and who makes the final decision?** (e.g., "Spoke with Bob, but CTO Sarah approves purchases")
- **Timeline or urgency?** (e.g., "Need solution by Q2", "Urgent priority")
- **Any competitors or alternatives they mentioned?**

The more details you provide, the better I can coach you on closing this deal! Feel free to paste raw notes or bullet points. 📝"""
