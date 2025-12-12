"""Parse notes node for MEDDPICC coach workflow.

Cleans and prepares raw sales call notes for analysis.
Detects and extracts content from URLs and documents.
"""

import logging
import re

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from .. import prompts
from ..state import MeddpiccAgentState

logger = logging.getLogger(__name__)


def extract_urls(text: str) -> list[str]:
    """Extract URLs from text.

    Args:
        text: Text to extract URLs from

    Returns:
        List of URLs found in text
    """
    # URL regex pattern
    url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    urls = re.findall(url_pattern, text)
    return urls


async def scrape_urls(urls: list[str]) -> tuple[str, list[str]]:
    """Scrape content from URLs using Tavily.

    Args:
        urls: List of URLs to scrape

    Returns:
        Tuple of (scraped_content, successful_sources)
    """
    from .services.search_clients import get_tavily_client

    tavily_client = get_tavily_client()

    if not tavily_client:
        logger.warning("Tavily client not available - skipping URL scraping")
        return "", []

    scraped_parts = []
    successful_sources = []

    for url in urls:
        try:
            result = await tavily_client.scrape_url(url)

            if result.get("success"):
                content = result.get("content", "")
                title = result.get("title", url)

                scraped_parts.append(f"## Source: {title}\nURL: {url}\n\n{content}\n\n")
                successful_sources.append(url)
                logger.info(f"Scraped {len(content)} chars from {url}")
            else:
                error = result.get("error", "Unknown error")
                logger.warning(f"Failed to scrape {url}: {error}")

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")

    scraped_content = "\n---\n\n".join(scraped_parts) if scraped_parts else ""
    return scraped_content, successful_sources


async def parse_notes(
    state: MeddpiccAgentState, config: RunnableConfig
) -> dict[str, str | list[str]]:
    """Parse and clean raw sales call notes, extracting content from URLs.

    Note: Document extraction (PDF, DOCX) is handled by the main bot handler
    and passed via context as document_content. This node focuses on URL scraping.

    Args:
        state: Current MEDDPICC agent state
        config: Runtime configuration

    Returns:
        Dict with updated state containing raw_notes, scraped_content, sources
    """
    query = state.get("query", "")

    # Check if we have document content from Slack file attachments
    # (extracted by main bot handler before routing to agent)
    configurable = config.get("configurable", {})
    document_content = configurable.get("document_content", "")

    logger.info(
        f"Parsing sales call notes ({len(query)} chars, {len(document_content)} chars from docs)"
    )

    # Step 1: Extract URLs from query
    urls = extract_urls(query)

    if urls:
        logger.info(f"Found {len(urls)} URLs in input: {urls}")

    # Step 2: Scrape URLs if found
    scraped_content = ""
    sources = []

    if urls:
        logger.info("Scraping URLs...")
        scraped_content, sources = await scrape_urls(urls)

        if sources:
            logger.info(
                f"Successfully scraped {len(sources)}/{len(urls)} URLs ({len(scraped_content)} chars)"
            )
        else:
            logger.warning("No URLs were successfully scraped")

    # Step 3: Clean the text notes (excluding URLs since we have their content)
    try:
        # Load only LLM settings (don't need full Settings which requires Slack)
        from config.settings import LLMSettings

        llm_settings = LLMSettings()
        llm = ChatOpenAI(  # type: ignore[call-arg]
            model="gpt-4o-mini",  # Simple task, use cheaper model
            temperature=0.1,
            model_kwargs={"max_tokens": 2000},
            api_key=llm_settings.api_key.get_secret_value(),
        )

        # If we have URLs, remove them from the text to avoid duplication
        text_to_clean = query
        if urls:
            for url in urls:
                text_to_clean = text_to_clean.replace(url, "[URL scraped]")

        prompt = prompts.parse_notes_prompt.format(query=text_to_clean)
        response = await llm.ainvoke(prompt)

        raw_notes = response.content if hasattr(response, "content") else str(response)
        logger.info(f"Notes parsed: {len(raw_notes)} chars")

    except Exception as e:
        logger.error(f"Parse notes error: {e}")
        # Fallback: use original query as-is
        raw_notes = query

    # Combine scraped content with document content from file attachments
    all_scraped_content = scraped_content
    if document_content:
        if all_scraped_content:
            all_scraped_content += (
                f"\n\n---\n\n## Document Attachments\n\n{document_content}"
            )
        else:
            all_scraped_content = f"## Document Attachments\n\n{document_content}"
        logger.info(f"Added {len(document_content)} chars from document attachments")

    return {  # type: ignore[return-value]
        "raw_notes": raw_notes,
        "scraped_content": all_scraped_content,
        "sources": sources,
    }
