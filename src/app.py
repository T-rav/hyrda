import os
import asyncio
import logging
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_sdk import WebClient

# Import our modules
from config.settings import Settings
from utils.logging import configure_logging
from services.llm_service import LLMService
from services.slack_service import SlackService
from handlers.event_handlers import register_handlers

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Slack app"""
    settings = Settings()
    
    # Initialize Slack app with token from settings
    app = AsyncApp(token=settings.slack.bot_token)
    
    # Create services
    client = app.client
    llm_service = LLMService(settings.llm)
    slack_service = SlackService(settings.slack, client)
    
    # Register event handlers
    asyncio.create_task(register_handlers(app, slack_service, llm_service))
    
    return app, slack_service, llm_service

async def maintain_presence(client: WebClient):
    """Keep the bot's presence status active"""
    while True:
        try:
            await client.users_setPresence(presence="auto")
            logger.debug("Updated bot presence status")
        except Exception as e:
            logger.error(f"Error updating presence: {e}")
        
        # Sleep for 5 minutes
        await asyncio.sleep(300)

async def run():
    """Start the Slack bot asynchronously"""
    # Display permission requirements warning
    logger.warning("=== PERMISSION REQUIREMENTS ===")
    logger.warning("To fully support thread responses, please ensure your Slack app has these permissions:")
    logger.warning("- groups:history (for private channels)")
    logger.warning("- mpim:history (for group DMs)")
    logger.warning("- channels:history (for public channels)")
    logger.warning("- im:history (for direct messages)")
    logger.warning("If missing any of these, reinstall your app at https://api.slack.com/apps")
    logger.warning("===============================")
    
    # Create and configure the app
    app, slack_service, llm_service = create_app()
    
    # Set bot presence to "auto" (online)
    try:
        auth_test = await app.client.auth_test()
        logger.info(f"Auth test response: {auth_test}")
        logger.info(f"Bot user ID: {auth_test.get('user_id')}")
        logger.info(f"Bot name: {auth_test.get('user')}")
        
        # Update bot ID if not set
        if not slack_service.bot_id:
            slack_service.bot_id = auth_test.get('user_id')
            logger.info(f"Updated bot ID to: {slack_service.bot_id}")
        
        # Set initial presence
        logger.info("Setting presence to 'auto'...")
        presence_response = await app.client.users_setPresence(presence="auto")
        logger.info(f"Presence API response: {presence_response}")
        
        # Start the presence maintenance task
        asyncio.create_task(maintain_presence(app.client))
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        import traceback
        logger.error(f"Startup error traceback: {traceback.format_exc()}")
    
    try:
        # Start the Socket Mode handler
        handler = AsyncSocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
        logger.info("Starting Insight Mesh Assistant...")
        await handler.start_async()
    except Exception as e:
        logger.error(f"Error starting socket mode: {e}")
        import traceback
        logger.error(f"Socket mode error traceback: {traceback.format_exc()}")
    finally:
        # Close services
        await llm_service.close()

def main():
    """Main entry point"""
    asyncio.run(run())

if __name__ == "__main__":
    main() 