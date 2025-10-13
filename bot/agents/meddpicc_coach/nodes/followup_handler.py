"""Follow-up questions handler node for MEDDPICC coach workflow.

Handles user follow-up questions after the initial analysis is complete,
allowing them to modify, clarify, or expand on the MEDDPICC analysis.
"""

import logging

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from agents.meddpicc_coach import prompts
from agents.meddpicc_coach.configuration import MeddpiccConfiguration
from agents.meddpicc_coach.state import MeddpiccAgentState

logger = logging.getLogger(__name__)


async def followup_handler(
    state: MeddpiccAgentState, config: RunnableConfig
) -> dict[str, str]:
    """Handle follow-up questions about the MEDDPICC analysis.

    Args:
        state: Current MEDDPICC agent state
        config: Runtime configuration

    Returns:
        Dict with updated state containing final_response
    """
    query = state.get("query", "").strip()
    original_analysis = state.get("original_analysis", "")

    logger.info(f"Handling follow-up question: {query[:100]}...")

    # If no query, something went wrong - return to user
    if not query:
        logger.warning("No follow-up question provided")
        return {  # type: ignore[return-value]
            "final_response": "I'm ready for your follow-up questions! What would you like to know or adjust?",
            "followup_mode": True,
        }

    # If no original analysis, we can't provide context
    if not original_analysis:
        logger.warning("No original analysis found for follow-up")
        return {  # type: ignore[return-value]
            "final_response": "I don't have the original analysis context. Please start a new analysis.",
            "followup_mode": False,
        }

    try:
        # Load configuration
        meddpicc_config = MeddpiccConfiguration.from_runnable_config(config)

        # Load only LLM settings
        from config.settings import LLMSettings

        llm_settings = LLMSettings()

        # Use GPT-4o for high-quality contextual responses
        llm = ChatOpenAI(  # type: ignore[call-arg]
            model="gpt-4o",
            temperature=meddpicc_config.coaching_temperature,
            model_kwargs={"max_tokens": meddpicc_config.coaching_max_tokens},
            api_key=llm_settings.api_key.get_secret_value(),
        )

        prompt = prompts.followup_handler_prompt.format(
            original_analysis=original_analysis, followup_question=query
        )
        response = await llm.ainvoke(prompt)

        followup_response = (
            response.content if hasattr(response, "content") else str(response)
        )
        logger.info(f"Follow-up response generated: {len(followup_response)} chars")

        # Check if LLM detected an unrelated question (exit signal)
        if followup_response.startswith("EXIT_FOLLOWUP_MODE:"):
            # Extract the message after the signal
            exit_message = followup_response.replace("EXIT_FOLLOWUP_MODE:", "").strip()
            logger.info("LLM detected unrelated question - exiting follow-up mode")
            return {  # type: ignore[return-value]
                "final_response": exit_message,
                "followup_mode": False,
            }

        # Keep follow-up mode active so user can ask more questions
        return {  # type: ignore[return-value]
            "final_response": followup_response,
            "followup_mode": True,
        }

    except Exception as e:
        logger.error(f"Follow-up handler error: {e}")
        return {  # type: ignore[return-value]
            "final_response": f"Sorry, I encountered an error processing your follow-up question: {str(e)}\n\nPlease try rephrasing your question.",
            "followup_mode": True,
        }
