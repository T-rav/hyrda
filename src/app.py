import os
import signal
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
from services.conversation_cache import ConversationCache
from services.user_prompt_service import UserPromptService
from handlers.event_handlers import register_handlers
from health import HealthChecker

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

# Global shutdown event
shutdown_event = asyncio.Event()

def create_app():
    """Create and configure the Slack app"""
    settings = Settings()
    
    # Initialize Slack app with token from settings
    app = AsyncApp(token=settings.slack.bot_token)
    
    # Create services
    client = app.client
    llm_service = LLMService(settings.llm)
    slack_service = SlackService(settings.slack, client)
    
    # Create conversation cache
    conversation_cache = None
    if settings.cache.enabled:
        conversation_cache = ConversationCache(
            redis_url=settings.cache.redis_url,
            ttl=settings.cache.conversation_ttl
        )
    
    # Create user prompt service
    prompt_service = None
    if settings.database.enabled:
        prompt_service = UserPromptService(settings.database.url)
    
    return app, slack_service, llm_service, conversation_cache, prompt_service

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

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()

async def run():
    """Start the Slack bot asynchronously with graceful shutdown"""
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Display permission requirements warning
    logger.warning("=== PERMISSION REQUIREMENTS ===")
    logger.warning("To fully support thread responses, please ensure your Slack app has these permissions:")
    logger.warning("- groups:history (for private channels)")
    logger.warning("- mpim:history (for group DMs)")
    logger.warning("- channels:history (for public channels)")
    logger.warning("- im:history (for direct messages)")
    logger.warning("If missing any of these, reinstall your app at https://api.slack.com/apps")
    logger.warning("===============================")
    
    settings = None
    health_checker = None
    handler = None
    llm_service = None
    prompt_service = None
    
    try:
        # Create and configure the app
        app, slack_service, llm_service, conversation_cache, prompt_service = create_app()
        settings = Settings()
        
        # Initialize prompt service database
        if prompt_service:
            await prompt_service.initialize()
            logger.info("User prompt database initialized")
        
        # Start health check server
        health_checker = HealthChecker(settings, conversation_cache)
        health_port = int(os.getenv("HEALTH_PORT", "8080"))
        await health_checker.start_server(health_port)
        logger.info(f"Health check server started on port {health_port}")
        
        # Register event handlers
        await register_handlers(app, slack_service, llm_service, conversation_cache, prompt_service)
        
        # Set bot presence to "auto" (online)
        try:
            auth_test = await app.client.auth_test()
            logger.info(f"Bot authenticated: {auth_test.get('user')} ({auth_test.get('user_id')})")
            
            # Update bot ID if not set
            if not slack_service.bot_id:
                slack_service.bot_id = auth_test.get('user_id')
                logger.info(f"Updated bot ID to: {slack_service.bot_id}")
            
            # Set initial presence
            await app.client.users_setPresence(presence="auto")
            logger.info("Bot presence set to online")
            
            # Start the presence maintenance task
            presence_task = asyncio.create_task(maintain_presence(app.client))
            
        except Exception as e:
            logger.error(f"Error during startup: {e}")
            raise
        
        # Start the Socket Mode handler
        handler = AsyncSocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
        logger.info("Starting Insight Mesh Assistant...")
        
        # Start handler in background
        handler_task = asyncio.create_task(handler.start_async())
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        logger.info("Shutdown signal received, cleaning up...")
        
        # Cancel background tasks
        if 'presence_task' in locals():
            presence_task.cancel()
        handler_task.cancel()
        
        # Wait for tasks to complete
        try:
            await asyncio.gather(presence_task, handler_task, return_exceptions=True)
        except Exception:
            pass
            
    except Exception as e:
        logger.error(f"Error in main application: {e}")
        import traceback
        logger.error(f"Application error traceback: {traceback.format_exc()}")
        raise
    finally:
        # Cleanup resources
        logger.info("Cleaning up resources...")
        
        if handler:
            try:
                await handler.close_async()
            except Exception as e:
                logger.error(f"Error closing socket handler: {e}")
                
        if llm_service:
            try:
                await llm_service.close()
            except Exception as e:
                logger.error(f"Error closing LLM service: {e}")
                
        if 'conversation_cache' in locals() and conversation_cache:
            try:
                await conversation_cache.close()
            except Exception as e:
                logger.error(f"Error closing conversation cache: {e}")
                
        if prompt_service:
            try:
                await prompt_service.close()
            except Exception as e:
                logger.error(f"Error closing user prompt service: {e}")
                
        if health_checker:
            try:
                await health_checker.stop_server()
            except Exception as e:
                logger.error(f"Error stopping health check server: {e}")
        
        logger.info("Shutdown complete")

def main():
    """Main entry point"""
    asyncio.run(run())

if __name__ == "__main__":
    main() 