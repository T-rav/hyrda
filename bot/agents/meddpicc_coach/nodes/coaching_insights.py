"""Coaching insights node for MEDDPICC coach workflow.

Generates Maverick's coaching advice and suggested questions.
"""

import logging

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from agents.meddpicc_coach import prompts
from agents.meddpicc_coach.configuration import MeddpiccConfiguration
from agents.meddpicc_coach.state import MeddpiccAgentState

logger = logging.getLogger(__name__)


async def coaching_insights(
    state: MeddpiccAgentState, config: RunnableConfig
) -> dict[str, str]:
    """Generate coaching insights and suggested questions.

    Args:
        state: Current MEDDPICC agent state
        config: Runtime configuration

    Returns:
        Dict with updated state containing coaching_insights and final_response
    """
    meddpicc_breakdown = state.get("meddpicc_breakdown", "")
    logger.info("Generating coaching insights")

    try:
        # Load configuration
        meddpicc_config = MeddpiccConfiguration.from_runnable_config(config)

        # Load only LLM settings (don't need full Settings which requires Slack)
        from config.settings import LLMSettings

        llm_settings = LLMSettings()

        # Use GPT-4o mini with higher temperature for creative coaching
        llm = ChatOpenAI(  # type: ignore[call-arg]
            model="gpt-4o-mini",
            temperature=meddpicc_config.coaching_temperature,
            model_kwargs={"max_tokens": meddpicc_config.coaching_max_tokens},
            api_key=llm_settings.api_key.get_secret_value(),
        )

        prompt = prompts.coaching_insights_prompt.format(
            meddpicc_breakdown=meddpicc_breakdown
        )
        response = await llm.ainvoke(prompt)

        coaching_insights = (
            response.content if hasattr(response, "content") else str(response)
        )
        logger.info(f"Coaching insights generated: {len(coaching_insights)} chars")

        # Combine MEDDPICC breakdown and coaching insights for final response
        # Add header if not present
        header = ":dart: **MEDDPICC**\n\n"
        if not meddpicc_breakdown.startswith(":dart:"):
            final_response = f"{header}{meddpicc_breakdown}\n\n{coaching_insights}"
        else:
            final_response = f"{meddpicc_breakdown}\n\n{coaching_insights}"

        # Store complete analysis for follow-up questions and enable follow-up mode
        original_analysis = final_response

        return {  # type: ignore[return-value]
            "coaching_insights": coaching_insights,
            "final_response": final_response,
            "original_analysis": original_analysis,
            "followup_mode": True,  # Enable follow-up mode after analysis
        }

    except Exception as e:
        logger.error(f"Coaching insights error: {e}")
        # Fallback: return just the breakdown without coaching
        return {  # type: ignore[return-value]
            "coaching_insights": "Error generating coaching insights. Please try again.",
            "final_response": meddpicc_breakdown,
        }
