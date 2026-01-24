"""Output node for profile agent - emits final standardized contract."""

import logging
from langchain_core.runnables import RunnableConfig
from ..state import ProfileAgentState

logger = logging.getLogger(__name__)


async def output_node(state: ProfileAgentState, config: RunnableConfig) -> dict:
    """Emit final output with standardized contract.

    This node runs after quality control passes and ensures the final
    output (message, attachments) is properly emitted for Slack display.

    Args:
        state: Current profile agent state

    Returns:
        Dict with message and attachments fields
    """
    logger.info("Emitting final output for Slack display")

    # Return the standardized contract fields from state
    # These were set by final_report_generation node
    message = state.get("message", "")
    attachments = state.get("attachments", [])
    followup_mode = state.get("followup_mode", False)

    logger.info(f"Output node returning: message={len(message)} chars, attachments={len(attachments)}, followup_mode={followup_mode}")

    return {
        "message": message,
        "attachments": attachments,
        "followup_mode": followup_mode
    }
