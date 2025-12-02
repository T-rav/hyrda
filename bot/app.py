import asyncio
import contextlib
import logging
import os
import signal
import traceback

from dotenv import load_dotenv
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk import WebClient

from config.settings import Settings
from handlers.event_handlers import register_handlers
from health import HealthChecker
from services import agent_registry
from services.conversation_cache import ConversationCache
from services.langfuse_service import get_langfuse_service
from services.llm_service import LLMService
from services.metrics_service import initialize_metrics_service
from services.prompt_service import initialize_prompt_service
from services.search_clients import close_search_clients, initialize_search_clients
from services.slack_service import SlackService
from utils.logging import configure_logging

# Load environment variables
load_dotenv()

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
    slack_service = SlackService(settings.slack, client)

    # Create conversation cache
    conversation_cache = None
    if settings.cache.enabled:
        conversation_cache = ConversationCache(
            redis_url=settings.cache.redis_url, ttl=settings.cache.conversation_ttl
        )

    # Initialize metrics service
    metrics_service = initialize_metrics_service(enabled=True)
    logger.info("Metrics service initialized")

    # Initialize prompt service
    initialize_prompt_service(settings)
    logger.info("Prompt service initialized")

    # Log registered agents
    registry = agent_registry.get_agent_registry()
    # Get unique agent names (registry has both primary names and aliases as keys)
    unique_agents = {
        info["name"] for info in registry.values() if info.get("is_primary", True)
    }
    logger.info(
        f"Registered {len(unique_agents)} agents: {', '.join(sorted(unique_agents))}"
    )

    # Create LLM service
    llm_service = LLMService(settings)

    return app, slack_service, llm_service, conversation_cache, metrics_service


async def maintain_presence(client: WebClient):
    """Keep the bot's presence status active.

    Uses asyncio.CancelledError to enable graceful shutdown without waiting
    for the full 5-minute sleep interval.
    """
    try:
        while True:
            try:
                await client.users_setPresence(presence="auto")  # type: ignore[misc]
                logger.debug("Updated bot presence status")
            except Exception as e:
                logger.error(f"Error updating presence: {e}")

            # Sleep for 5 minutes, but allow cancellation
            await asyncio.sleep(300)
    except asyncio.CancelledError:
        logger.info("Presence maintenance task cancelled, shutting down gracefully")
        raise  # Re-raise to properly cancel the task


def signal_handler(signum, _):
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
    logger.warning(
        "To fully support thread responses, please ensure your Slack app has these permissions:"
    )
    logger.warning("- groups:history (for private channels)")
    logger.warning("- mpim:history (for group DMs)")
    logger.warning("- channels:history (for public channels)")
    logger.warning("- im:history (for direct messages)")
    logger.warning(
        "If missing any of these, reinstall your app at https://api.slack.com/apps"
    )
    logger.warning("===============================")

    settings = None
    health_checker = None
    handler = None
    llm_service = None

    try:
        # Create and configure the app
        app, slack_service, llm_service, conversation_cache, metrics_service = (
            create_app()
        )
        settings = Settings()

        # Initialize LLM service (includes RAG)
        await llm_service.initialize()
        logger.info("LLM service initialized")

        # Initialize search clients (Tavily + Perplexity)
        await initialize_search_clients(
            tavily_api_key=settings.search.tavily_api_key,
            perplexity_api_key=settings.search.perplexity_api_key,
        )
        logger.info("✅ Search clients initialized (Tavily + Perplexity)")

        # Start health check server
        langfuse_service = get_langfuse_service()
        # If global langfuse service is None, get it directly from LLM service
        if langfuse_service is None:
            langfuse_service = llm_service.langfuse_service
        health_checker = HealthChecker(settings, conversation_cache, langfuse_service)
        health_port = int(os.getenv("HEALTH_PORT", "8080"))
        await health_checker.start_server(health_port)
        logger.info(f"Health check server started on port {health_port}")
        logger.info(f"Metrics available at: http://localhost:{health_port}/prometheus")

        # Register event handlers
        await register_handlers(app, slack_service, llm_service, conversation_cache)

        # Set bot presence to "auto" (online)
        try:
            auth_test = await app.client.auth_test()
            logger.info(
                f"Bot authenticated: {auth_test.get('user')} ({auth_test.get('user_id')})"
            )

            # Update bot ID if not set
            if not slack_service.bot_id:
                slack_service.bot_id = auth_test.get("user_id")
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
        if "presence_task" in locals():
            presence_task.cancel()
        handler_task.cancel()

        # Wait for tasks to complete
        with contextlib.suppress(Exception):
            await asyncio.gather(presence_task, handler_task, return_exceptions=True)

    except Exception as e:
        logger.error(f"Error in main application: {e}")

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

        # Close search clients
        try:
            await close_search_clients()
            logger.info("Search clients closed")
        except Exception as e:
            logger.error(f"Error closing search clients: {e}")

        if "conversation_cache" in locals() and conversation_cache:
            try:
                await conversation_cache.close()
            except Exception as e:
                logger.error(f"Error closing conversation cache: {e}")

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
