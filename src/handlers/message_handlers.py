import logging
from typing import List, Dict, Any, Optional

from slack_sdk import WebClient
from services.llm_service import LLMService
from services.slack_service import SlackService
from services.formatting import MessageFormatter
from handlers.agent_processes import run_agent_process, get_agent_blocks
from utils.errors import handle_error

logger = logging.getLogger(__name__)

SYSTEM_MESSAGE = """You are a helpful assistant for Insight Mesh, a RAG (Retrieval-Augmented Generation) system. You help users understand and work with their data. You can also start agent processes on behalf of users when they request it."""

async def handle_message(
    text: str,
    user_id: str,
    slack_service: SlackService,
    llm_service: LLMService,
    channel: str,
    thread_ts: Optional[str] = None
):
    """Handle an incoming message from Slack"""
    logger.info(f"Handling message: '{text}' from user {user_id} in channel {channel}, thread {thread_ts}")
    
    # For tracking the thinking indicator message
    thinking_message_ts = None
    
    try:
        # Log thread info
        if thread_ts:
            logger.info(f"Responding in existing thread: {thread_ts}")
        else:
            logger.info("Starting a new thread")
            
        # Post a thinking message (we'll delete this later)
        thinking_message_ts = await slack_service.send_thinking_indicator(channel, thread_ts)
            
        # Retrieve thread history if this is a message in a thread
        thread_messages = []
        if thread_ts and thread_ts != "None":
            thread_messages, success = await slack_service.get_thread_history(channel, thread_ts)
            
        # Prepare the LLM request
        llm_messages = await prepare_llm_messages(text, thread_messages)
        
        # Get the LLM response
        llm_response = await llm_service.get_response(
            messages=llm_messages,
            user_id=user_id
        )
        
        # Delete the thinking message
        await slack_service.delete_thinking_indicator(channel, thinking_message_ts)
        thinking_message_ts = None
            
        # Send the response
        if llm_response:
            logger.info(f"Sending response to Slack: channel={channel}, thread_ts={thread_ts}")
            
            # Format the response for better rendering in Slack
            formatted_response = await MessageFormatter.format_message(llm_response)
            
            await slack_service.send_message(
                channel=channel,
                text=formatted_response,
                thread_ts=thread_ts
            )
            logger.info(f"Response sent successfully")
        else:
            logger.error("No LLM response received, sending error message")
            await slack_service.send_message(
                channel=channel,
                text="I'm sorry, I encountered an error while generating a response.",
                thread_ts=thread_ts
            )
                
    except Exception as e:
        # Handle any errors
        await handle_error(
            slack_service.client, 
            channel, 
            thread_ts, 
            e, 
            "I'm sorry, something went wrong. Please try again later."
        )
        
        # Delete the thinking message if there was an error
        if thinking_message_ts:
            await slack_service.delete_thinking_indicator(channel, thinking_message_ts)

async def prepare_llm_messages(
    text: str,
    thread_messages: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    """Prepare messages for the LLM API call"""
    # Start with system message
    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
    ]
    
    # Add thread history if available
    if thread_messages:
        messages.extend(thread_messages)
        logger.info("Added thread history to context")
    
    # Add current message if it's not already included in thread history
    if text and (not thread_messages or thread_messages[-1]["content"] != text):
        messages.append({"role": "user", "content": text})
    
    logger.info(f"Prepared {len(messages)} messages for LLM API")
    return messages

async def handle_agent_action(
    action_id: str,
    user_id: str,
    slack_service: SlackService,
    channel: str,
    thread_ts: str
):
    """Handle agent process actions"""
    logger.info(f"Handling agent action: {action_id}")
    
    # Show thinking indicator
    thinking_message = await slack_service.send_thinking_indicator(channel, thread_ts)
    
    # Run the agent process
    result = await run_agent_process(action_id)
    
    # Delete thinking message
    await slack_service.delete_thinking_indicator(channel, thinking_message)
    
    # Create a rich message with process info
    blocks = get_agent_blocks(result, user_id)
    
    # Determine the fallback text based on success
    text = f"Agent process {result.get('name', action_id)} started successfully." if result.get("success") else f"Failed to start agent process: {result.get('error', 'Unknown error')}"
    
    # Send the response
    await slack_service.send_message(
        channel=channel,
        text=text,
        thread_ts=thread_ts,
        blocks=blocks
    ) 