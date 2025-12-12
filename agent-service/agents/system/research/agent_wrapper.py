"""Streaming wrapper for research agent graph.

Provides stream() method for real-time step emission to Slack.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from langchain_core.messages import AIMessage

from .research_agent import research_agent

logger = logging.getLogger(__name__)


class ResearchAgentWrapper:
    """Wrapper that adds streaming support to research agent graph."""

    def __init__(self):
        """Initialize with compiled graph."""
        self.graph = research_agent

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        """Non-streaming execution (backwards compatibility).

        Args:
            query: Research query
            context: Agent context (thread_ts, channel, etc.)

        Returns:
            Dict with response, pdf_url, and metadata
        """
        # Prepare initial state
        initial_state = {
            "query": query,
            "research_depth": context.get("research_depth", "standard"),
        }

        # Run graph (non-streaming)
        config = {"recursion_limit": 100}
        if context.get("thread_ts"):
            config["configurable"] = {"thread_id": context["thread_ts"]}

        result = await self.graph.ainvoke(initial_state, config)

        # Format response
        final_report = result.get("final_report", "")
        executive_summary = result.get("executive_summary", "")
        pdf_url = result.get("pdf_url", "")

        response = f"{executive_summary}\n\n📎 **Download Full Report:** {pdf_url}" if pdf_url else executive_summary

        return {
            "response": response,
            "pdf_url": pdf_url,
            "metadata": {
                "tasks_completed": len(result.get("completed_tasks", [])),
                "report_length": len(final_report),
            },
        }

    async def invoke(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        """Invoke agent (alias for run() for compatibility).

        Args:
            query: Research query
            context: Agent context

        Returns:
            Dict with response and metadata
        """
        return await self.run(query, context)

    async def stream(
        self, query: str, context: dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """Stream execution with real-time step updates.

        Args:
            query: Research query
            context: Agent context (thread_ts, channel, etc.)

        Yields:
            String updates for each node execution
        """
        logger.info(f"Streaming research agent for query: {query[:100]}")

        # Prepare initial state
        initial_state = {
            "query": query,
            "research_depth": context.get("research_depth", "standard"),
        }

        # Configure with thread_id for checkpointing
        config = {"recursion_limit": 100}
        if context.get("thread_ts"):
            config["configurable"] = {"thread_id": context["thread_ts"]}

        # Stream graph execution and track final state
        final_state = {}
        try:
            async for event in self.graph.astream(initial_state, config):
                # event is a dict: {node_name: output_state}
                for node_name, output in event.items():
                    # Track final state
                    final_state = output

                    # Format update based on node
                    update = self._format_node_update(node_name, output)
                    if update:
                        yield update

            # Final summary with PDF link (extracted from last state)
            pdf_url = final_state.get("pdf_url", "")
            executive_summary = final_state.get("executive_summary", "")

            if executive_summary:
                yield f"\n\n## Executive Summary\n\n{executive_summary}"

            if pdf_url:
                yield f"\n\n📎 **Download Full Report:** {pdf_url}"

        except Exception as e:
            logger.error(f"Error streaming research agent: {e}", exc_info=True)
            yield f"\n\n❌ **Error:** {str(e)}"

    def _format_node_update(self, node_name: str, output: dict[str, Any]) -> str | None:
        """Format node execution into user-friendly update.

        Args:
            node_name: Name of executed node
            output: Node output state

        Returns:
            Formatted update string or None if no update needed
        """
        # Map node names to user-friendly messages
        if node_name == "create_research_plan":
            task_count = len(output.get("research_tasks", []))
            return f"📋 **Planning:** Created {task_count} research tasks"

        elif node_name == "research_supervisor":
            completed = len(output.get("completed_tasks", []))
            total = len(output.get("research_tasks", []))
            if completed > 0:
                return f"🔍 **Researching:** {completed}/{total} tasks complete"

        elif node_name == "synthesize_findings":
            report_length = len(output.get("final_report", ""))
            return f"✍️ **Synthesizing:** Generated {report_length:,} character report"

        elif node_name == "quality_control":
            passes = output.get("passes_quality", False)
            if passes:
                return "✅ **Quality Check:** Report approved"
            else:
                revision = output.get("revision_count", 0)
                return f"🔄 **Quality Check:** Revision {revision} in progress"

        # Check for messages added by nodes
        messages = output.get("messages", [])
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, AIMessage):
                content = last_message.content
                if content and len(content) < 200:  # Short status messages
                    return f"💬 {content}"

        return None


logger.info("Research agent wrapper loaded")
