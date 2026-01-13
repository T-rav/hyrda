"""MEDDPICC analysis node for MEDDPICC coach workflow.

Structures sales notes into MEDDPICC format.
"""

import logging

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from meddpicc_coach import prompts
from meddpicc_coach.configuration import MeddpiccConfiguration
from meddpicc_coach.state import MeddpiccAgentState

logger = logging.getLogger(__name__)


async def meddpicc_analysis(
    state: MeddpiccAgentState, config: RunnableConfig
) -> dict[str, str]:
    """Analyze notes and structure into MEDDPICC framework.

    Args:
        state: Current MEDDPICC agent state
        config: Runtime configuration

    Returns:
        Dict with updated state containing meddpicc_breakdown

    """
    raw_notes = state.get("raw_notes", "")
    scraped_content = state.get("scraped_content", "")
    sources = state.get("sources", [])

    # Combine raw notes and scraped content
    combined_notes = raw_notes
    if scraped_content:
        combined_notes = f"{raw_notes}\n\n---\n\n## Additional Context from URLs\n\n{scraped_content}"
        logger.info(
            f"Performing MEDDPICC analysis on {len(raw_notes)} chars notes + {len(scraped_content)} chars scraped content from {len(sources)} sources"
        )
    else:
        logger.info("Performing MEDDPICC analysis on text notes only")

    try:
        # Load configuration
        meddpicc_config = MeddpiccConfiguration.from_runnable_config(config)

        # Load only LLM settings (don't need full Settings which requires Slack)
        from config.settings import LLMSettings

        llm_settings = LLMSettings()

        # Use GPT-4o for higher quality analysis
        llm = ChatOpenAI(  # type: ignore[call-arg]
            model="gpt-4o",
            temperature=meddpicc_config.analysis_temperature,
            model_kwargs={"max_tokens": meddpicc_config.analysis_max_tokens},
            api_key=llm_settings.api_key.get_secret_value(),
        )

        prompt = prompts.meddpicc_analysis_prompt.format(raw_notes=combined_notes)
        response = await llm.ainvoke(prompt)

        meddpicc_breakdown = (
            response.content if hasattr(response, "content") else str(response)
        )

        # Add sources footer if we have scraped content
        if sources:
            sources_text = "\n\n---\n\n**📎 Sources Analyzed:**\n"
            for i, url in enumerate(sources, 1):
                sources_text += f"{i}. {url}\n"
            meddpicc_breakdown += sources_text

        logger.info(f"MEDDPICC analysis complete: {len(meddpicc_breakdown)} chars")

        return {"meddpicc_breakdown": meddpicc_breakdown}  # type: ignore[return-value]

    except Exception as e:
        logger.error(f"MEDDPICC analysis error: {e}")
        return {  # type: ignore[return-value]
            "meddpicc_breakdown": f"Error during MEDDPICC analysis: {str(e)}\n\nPlease try again."
        }
