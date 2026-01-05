"""Answer question node for follow-up questions about existing profile.

Handles conversational follow-up questions by referencing the already-generated
final report instead of re-running the entire research workflow.
"""

import logging
from datetime import datetime

from langchain_core.runnables import RunnableConfig

from ..configuration import ProfileConfiguration
from ..state import ProfileAgentState
from ..utils import create_human_message, create_system_message

logger = logging.getLogger(__name__)


async def answer_question(state: ProfileAgentState, config: RunnableConfig) -> dict:
    """Answer follow-up question using existing profile report.

    Args:
        state: Current profile agent state with final_report
        config: Runtime configuration

    Returns:
        Dict with message containing the answer
    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    query = state.get("query", "")
    final_report = state.get("final_report", "")
    focus_area = state.get("focus_area", "")

    logger.info(f"Answering follow-up question: '{query[:100]}...'")

    if not final_report:
        logger.error("No final_report in state - cannot answer question")
        return {
            "message": "❌ I don't have a profile report to reference. Please start with a profile request first (e.g., 'profile [company name]')."
        }

    # Use LLM to answer question based on report
    from config.settings import Settings

    settings = Settings()

    # Use same LLM as final report generation
    llm = None
    if settings.gemini.enabled and settings.gemini.api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            logger.info(f"Using Gemini ({settings.gemini.model}) for Q&A")
            llm = ChatGoogleGenerativeAI(
                model=settings.gemini.model,
                google_api_key=settings.gemini.api_key,
                temperature=0.3,  # Slightly higher for natural conversation
                max_output_tokens=2000,  # Shorter answers for Q&A
            )
        except ImportError:
            logger.warning("langchain_google_genai not installed - falling back to OpenAI")

    if llm is None:
        from langchain_openai import ChatOpenAI

        logger.info(f"Using OpenAI ({settings.llm.model}) for Q&A")
        llm = ChatOpenAI(
            model=settings.llm.model,
            api_key=settings.llm.api_key,
            temperature=0.3,
            max_completion_tokens=2000,
        )

    # Build Q&A prompt
    system_prompt = f"""You are a helpful assistant answering questions about a company profile.

You have access to a comprehensive profile report about the company. Use this report to answer the user's question accurately and concisely.

**IMPORTANT INSTRUCTIONS:**
- Answer based ONLY on information in the report below
- If the information is not in the report, say "I don't have information about that in the profile"
- Be conversational and helpful
- Cite specific sections when relevant (e.g., "According to the Technology section...")
- Keep answers concise but complete (2-4 paragraphs)

**PROFILE REPORT:**
{final_report}

**FOCUS AREA:** {focus_area if focus_area else "General profile"}

Current date: {datetime.now().strftime("%B %d, %Y")}
"""

    user_prompt = f"Question: {query}"

    messages = [
        create_system_message(system_prompt),
        create_human_message(user_prompt),
    ]

    try:
        response = await llm.ainvoke(messages)
        answer = response.content if hasattr(response, "content") else str(response)

        logger.info(f"Generated answer: {len(answer)} characters")

        # Return standardized output
        return {
            "message": answer,
            "attachments": [],  # No attachments for Q&A
        }

    except Exception as e:
        logger.error(f"Failed to answer question: {e}")
        return {
            "message": f"❌ Failed to answer question: {str(e)}\n\nPlease try rephrasing your question."
        }
