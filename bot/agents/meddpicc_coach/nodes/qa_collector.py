"""Q&A collector node for gathering MEDDPICC information interactively.

Asks questions one by one and collects answers before building the report.
"""

import logging

from langchain_core.runnables import RunnableConfig

from agents.meddpicc_coach.state import MeddpiccAgentState

logger = logging.getLogger(__name__)

# MEDDPICC questions to ask
MEDDPICC_QUESTIONS = [
    (
        "company",
        "**Who's the company/contact?** (Name, industry, size - say 'skip' if you don't know)",
    ),
    (
        "pain",
        "**What problems are they trying to solve?** (Business pain points, frustrations - or 'skip')",
    ),
    (
        "metrics",
        "**Any numbers or goals mentioned?** (Revenue targets, time savings, KPIs - or 'skip')",
    ),
    (
        "buyer",
        "**Who's the decision maker?** (Title, role, who controls budget - or 'skip')",
    ),
    (
        "criteria",
        "**How are they evaluating solutions?** (Requirements, must-haves - or 'skip')",
    ),
    (
        "process",
        "**What's their buying process?** (Timeline, approval steps - or 'skip')",
    ),
    (
        "champion",
        "**Who's your internal advocate?** (Someone pushing for your solution - or 'skip')",
    ),
    (
        "competition",
        "**What alternatives are they considering?** (Other vendors, status quo - or 'skip')",
    ),
]


async def qa_collector(state: MeddpiccAgentState, config: RunnableConfig) -> dict:
    """Collect answers to MEDDPICC questions interactively.

    Args:
        state: Current MEDDPICC agent state
        config: Runtime configuration

    Returns:
        Dict with updated state

    """
    query = state.get("query", "").strip()
    question_mode = state.get("question_mode", False)
    current_question_index = state.get("current_question_index", 0)
    gathered_answers = state.get("gathered_answers", {})

    logger.info(
        f"Q&A Collector - mode={question_mode}, question={current_question_index}, query_len={len(query)}"
    )

    # If this is first call (no query, not in question mode), initialize Q&A mode
    if not query and not question_mode:
        logger.info("Starting Q&A mode - asking first question")
        next_question = MEDDPICC_QUESTIONS[0][1]
        return {
            "question_mode": True,
            "current_question_index": 1,  # Next question to ask
            "gathered_answers": {},
            "final_response": f"🎯 **MEDDPICC Analysis** - Question 1/{len(MEDDPICC_QUESTIONS)}\n\n{next_question}",
        }

    # If in question mode and we have a response, store it
    if question_mode and query and current_question_index > 0:
        prev_key = MEDDPICC_QUESTIONS[current_question_index - 1][0]
        gathered_answers[prev_key] = query
        logger.info(f"💾 Stored answer for {prev_key}: {query[:50]}...")

        # Check if we're done with all questions
        if current_question_index >= len(MEDDPICC_QUESTIONS):
            logger.info("✅ All questions answered, compiling notes")

            # Build notes from gathered answers
            notes_parts = []
            for key, _question_text in MEDDPICC_QUESTIONS:
                answer = gathered_answers.get(key, "Not provided")
                if answer.lower() not in [
                    "skip",
                    "idk",
                    "i don't know",
                    "don't know",
                    "",
                ]:
                    notes_parts.append(f"**{key.title()}:** {answer}")

            compiled_notes = (
                "\n\n".join(notes_parts)
                if notes_parts
                else "No detailed information provided."
            )

            # Exit Q&A mode and set query to compiled notes for analysis
            return {
                "question_mode": False,
                "current_question_index": 0,
                "gathered_answers": {},
                "query": compiled_notes,
                "raw_notes": compiled_notes,
            }
        else:
            # Ask next question
            next_question = MEDDPICC_QUESTIONS[current_question_index][1]
            progress = (
                f"Question {current_question_index + 1}/{len(MEDDPICC_QUESTIONS)}"
            )
            logger.info(f"Asking question {current_question_index + 1}")

            return {
                "question_mode": True,
                "current_question_index": current_question_index + 1,
                "gathered_answers": gathered_answers,
                "final_response": f"🎯 **MEDDPICC Analysis** - {progress}\n\n{next_question}",
            }

    # Should not reach here, but handle gracefully
    logger.warning(
        f"Unexpected state in qa_collector: mode={question_mode}, index={current_question_index}"
    )
    return {}
