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
    conversation_history = state.get("conversation_history", [])
    conversation_summary = state.get("conversation_summary", "")

    logger.info(f"Answering follow-up question: '{query[:100]}...'")
    logger.info(f"Conversation context: {len(conversation_history)} turns, summary: {len(conversation_summary)} chars")

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

    # Build conversation context from history
    conversation_context = ""
    if conversation_summary:
        conversation_context += f"\n**CONVERSATION SUMMARY:**\n{conversation_summary}\n"

    if conversation_history:
        conversation_context += "\n**RECENT CONVERSATION:**\n"
        # Include last 5 turns for immediate context
        recent_turns = conversation_history[-5:]
        for turn in recent_turns:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            conversation_context += f"{role.upper()}: {content}\n"

    # Build Q&A prompt with intent detection
    system_prompt = f"""You are a helpful assistant answering questions about a company profile.

You have access to a comprehensive profile report about the company. Use this report to answer the user's question accurately and concisely.

**IMPORTANT INSTRUCTIONS:**
- Answer based ONLY on information in the report below
- If the information is not in the report, say "I don't have information about that in the profile"
- Be conversational and helpful
- Cite specific sections when relevant (e.g., "According to the Technology section...")
- Keep answers concise but complete (2-4 paragraphs)
- Use conversation history to maintain context and avoid repeating yourself

**INTENT DETECTION:**
After answering, determine the user's intent for continuing the conversation:
- If they're asking another substantive question about the profile → intent: "continue"
- If they're thanking you, saying goodbye, or expressing completion (e.g., "thanks", "that's all", "perfect") → intent: "exit"
- If unclear, default to "continue"

**OUTPUT FORMAT:**
Return a JSON object with:
{{
    "intent": "continue" or "exit",
    "message": "your helpful answer here"
}}
{conversation_context}
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
        # Use JSON mode for structured intent detection (like MEDDIC)
        if hasattr(llm, "model_kwargs"):
            llm.model_kwargs = {"response_format": {"type": "json_object"}}

        response = await llm.ainvoke(messages)
        response_content = response.content if hasattr(response, "content") else str(response)

        logger.info(f"Generated response: {len(response_content)} characters")

        # Parse JSON response
        import json
        try:
            parsed = json.loads(response_content)
            intent = parsed.get("intent", "continue")
            answer = parsed.get("message", response_content)

            logger.info(f"Intent detected: {intent}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}, using raw content")
            # Fallback: treat as continue if JSON parsing fails
            intent = "continue"
            answer = response_content

        # Determine followup_mode based on intent
        followup_mode = (intent == "continue")

        # Update conversation history with this turn
        updated_history = conversation_history.copy() if conversation_history else []
        updated_history.append({"role": "user", "content": query})
        updated_history.append({"role": "assistant", "content": answer})

        logger.info(f"Updated conversation history: {len(updated_history)} total turns")

        # Phase 3: Summarize older conversation if history gets too long (>10 turns = 20 messages)
        updated_summary = conversation_summary
        if len(updated_history) > 20:
            logger.info(f"Conversation history exceeds 20 messages - summarizing older turns")

            # Summarize the oldest 12 messages (6 turns), keep recent 8 messages (4 turns)
            to_summarize = updated_history[:12]
            to_keep = updated_history[12:]

            # Create summary of older messages
            summary_prompt = f"""Summarize this conversation concisely, focusing on key questions asked and information provided:

{chr(10).join([f"{turn['role'].upper()}: {turn['content']}" for turn in to_summarize])}

Provide a brief 2-3 sentence summary of the main topics discussed and information shared."""

            try:
                summary_response = await llm.ainvoke([create_human_message(summary_prompt)])
                new_summary_part = (
                    summary_response.content
                    if hasattr(summary_response, "content")
                    else str(summary_response)
                )

                # Append to existing summary if present
                if updated_summary:
                    updated_summary += f"\n\n{new_summary_part}"
                else:
                    updated_summary = new_summary_part

                updated_history = to_keep  # Keep only recent turns
                logger.info(f"Summarized {len(to_summarize)} messages, keeping {len(to_keep)} recent messages")

            except Exception as summary_error:
                logger.warning(f"Failed to summarize conversation: {summary_error}, keeping full history")

        # Return standardized output with followup control and updated history
        return {
            "message": answer,
            "attachments": [],  # No attachments for Q&A
            "followup_mode": followup_mode,  # Control whether to stay in follow-up
            "conversation_history": updated_history,  # Track full conversation
            "conversation_summary": updated_summary,  # Semantic summary of older turns
        }

    except Exception as e:
        logger.error(f"Failed to answer question: {e}")
        return {
            "message": f"❌ Failed to answer question: {str(e)}\n\nPlease try rephrasing your question."
        }
