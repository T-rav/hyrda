"""
Query Rewriting Service

Adaptive query rewriter that uses different strategies based on query intent
to improve RAG retrieval accuracy. Supports:
- HyDE (Hypothetical Document Embeddings) for allocation queries
- Semantic expansion for structured data queries
- Lightweight rewrites for general queries
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class AdaptiveQueryRewriter:
    """
    Multi-strategy query rewriter that adapts to query type.

    Uses a two-step approach:
    1. Classify query intent (single LLM call)
    2. Apply appropriate rewriting strategy
    """

    # Synonym mappings for semantic expansion
    SEMANTIC_SYNONYMS = {
        "project": ["project", "initiative", "work", "engagement", "program"],
        "client": ["client", "customer", "company", "organization", "account"],
        "engineer": ["engineer", "developer", "team member", "staff", "consultant"],
        "allocation": [
            "allocation",
            "assignment",
            "staffing",
            "team composition",
            "resource",
        ],
    }

    def __init__(self, llm_service, enable_rewriting: bool = True):
        """
        Initialize query rewriter.

        Args:
            llm_service: LLM service for query rewriting
            enable_rewriting: Whether to enable query rewriting (default: True)
        """
        self.llm_service = llm_service
        self.enable_rewriting = enable_rewriting

    async def rewrite_query(
        self, query: str, conversation_history: list[dict] | None = None
    ) -> dict[str, Any]:
        """
        Rewrite query using adaptive strategy based on intent.

        Args:
            query: Original user query
            conversation_history: Recent conversation messages for context

        Returns:
            Dictionary with:
                - query: Rewritten query string
                - original_query: Original query
                - filters: Metadata filters to apply
                - strategy: Strategy used ("hyde", "semantic", "passthrough")
                - intent: Classified intent information
        """
        if not self.enable_rewriting:
            return {
                "query": query,
                "original_query": query,
                "filters": {},
                "strategy": "disabled",
                "intent": {},
            }

        try:
            # Step 1: Classify query intent
            intent = await self._classify_intent(query, conversation_history or [])

            logger.info(
                f"Query intent: {intent.get('type')} (confidence: {intent.get('confidence', 0):.2f})"
            )

            # Step 2: Apply appropriate strategy
            if (
                intent["type"] == "team_allocation"
                and intent.get("confidence", 0) > 0.7
            ):
                result = await self._hyde_rewrite(query, intent)
            elif intent["type"] in ["project_info", "client_info"]:
                result = await self._semantic_rewrite(query, intent)
            elif intent["type"] == "document_search":
                result = await self._expand_query(query, intent)
            else:
                result = await self._lightweight_rewrite(query, intent)

            result["original_query"] = query
            result["intent"] = intent

            logger.debug(
                f"Query rewritten using {result['strategy']} strategy: '{query}' → '{result['query'][:100]}...'"
            )

            return result

        except Exception as e:
            logger.warning(f"Query rewriting failed: {e}. Using original query.")
            return {
                "query": query,
                "original_query": query,
                "filters": {},
                "strategy": "error_fallback",
                "intent": {},
            }

    async def _classify_intent(
        self, query: str, conversation_history: list[dict]
    ) -> dict[str, Any]:
        """
        Classify query intent to determine rewriting strategy.

        Args:
            query: User query
            conversation_history: Recent conversation context

        Returns:
            Dictionary with intent classification
        """
        # Format recent conversation history (last 3 messages)
        history_context = self._format_history(conversation_history[-3:])

        prompt = f"""Classify the intent of this user query to optimize information retrieval.

Query: "{query}"

Recent conversation context:
{history_context}

Analyze the query and return a JSON object with:
{{
  "type": "<intent_type>",
  "entities": ["<entity1>", "<entity2>"],
  "time_range": {{"start": "YYYY-MM-DD or null", "end": "YYYY-MM-DD or null"}},
  "confidence": <0.0-1.0>
}}

Intent types:
- "team_allocation": Questions about WHO worked/works on projects, team members, staffing, engineers
- "project_info": Questions about project details, status, timeline, deliverables
- "client_info": Questions about clients, contracts, relationships, accounts
- "document_search": Looking for specific documents, files, reports, diagrams
- "general": Everything else (technical questions, how-to, explanations)

Rules:
1. Use "team_allocation" for queries about people on projects (e.g., "who worked on X", "engineers on Y")
2. Extract entities: project names, client names, person names mentioned in query
3. Infer time ranges from phrases like "in 2023", "last year", "currently"
4. Set confidence based on how clearly the query matches an intent type
5. Return ONLY valid JSON, no explanation

Examples:
Query: "who were the engineers on Ticketmaster projects?"
{{"type": "team_allocation", "entities": ["Ticketmaster"], "time_range": {{"start": null, "end": null}}, "confidence": 0.95}}

Query: "show me the architecture diagram for the API"
{{"type": "document_search", "entities": ["API", "architecture"], "time_range": {{"start": null, "end": null}}, "confidence": 0.9}}

Query: "what is the status of project X?"
{{"type": "project_info", "entities": ["project X"], "time_range": {{"start": null, "end": null}}, "confidence": 0.85}}

Now classify this query. Return ONLY the JSON object:"""

        response = await self.llm_service.generate_response(
            prompt=prompt, max_tokens=200, temperature=0.1
        )

        try:
            # Try to parse JSON from response
            intent = json.loads(response.strip())
            return intent
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            logger.warning(f"Failed to parse intent JSON: {response}")
            return {
                "type": "general",
                "entities": [],
                "time_range": {"start": None, "end": None},
                "confidence": 0.5,
            }

    async def _hyde_rewrite(self, query: str, intent: dict) -> dict[str, Any]:
        """
        HyDE (Hypothetical Document Embeddings) rewrite for allocation queries.

        Generates a hypothetical allocation record that would answer the query,
        then searches for records similar to this hypothetical one.

        Args:
            query: Original query
            intent: Intent classification

        Returns:
            Rewrite result with hypothetical document
        """
        entities = intent.get("entities", [])
        entity_context = f" for {entities[0]}" if entities else ""

        prompt = f"""Generate a sample employee allocation record that would answer: "{query}"

Create a realistic allocation record{entity_context}. Format it like this:

Team Member Allocation: [Full Name] ([email])
Role: Engineer/Developer working on [Project Name]
Client: [Client Name]
Practice Area: [Practice Area]
Delivery Owner: [Owner Name]
Project Type: BILLABLE
Allocation Period: [start date] to [end date]

Summary: [Name] is an engineer who worked on the [Project] project for [Client]. This team member was allocated to [Project] under delivery owner [Owner] in the [Practice] practice area. As a developer on this project, [Name] contributed engineering work from [start] to [end].

Make it specific to the query context. Use realistic names, dates, and details."""

        hypothetical_doc = await self.llm_service.generate_response(
            prompt=prompt, max_tokens=300, temperature=0.3
        )

        return {
            "query": hypothetical_doc.strip(),
            "filters": {"record_type": "allocation"},
            "strategy": "hyde",
        }

    async def _semantic_rewrite(self, query: str, intent: dict) -> dict[str, Any]:
        """
        Semantic expansion for structured data queries.

        Adds synonyms and related terms to improve matching.

        Args:
            query: Original query
            intent: Intent classification

        Returns:
            Rewrite result with expanded query
        """
        entities = intent.get("entities", [])
        entity_str = " ".join(entities)

        # Build expanded terms from synonyms
        expanded_terms = set()
        query_lower = query.lower()

        for key, synonyms in self.SEMANTIC_SYNONYMS.items():
            if key in query_lower:
                expanded_terms.update(synonyms)

        # Add entities and synonyms to query
        expansion = " ".join(expanded_terms)
        rewritten = f"{query} {entity_str} {expansion}".strip()

        # Build filters
        filters = {}
        if intent["type"] == "project_info":
            filters["record_type"] = "project"
        elif intent["type"] == "client_info":
            filters["record_type"] = "client"

        # Add time range filters if available
        time_range = intent.get("time_range", {})
        if time_range.get("start"):
            filters["start_date"] = time_range["start"]
        if time_range.get("end"):
            filters["end_date"] = time_range["end"]

        return {"query": rewritten, "filters": filters, "strategy": "semantic"}

    async def _expand_query(self, query: str, intent: dict) -> dict[str, Any]:
        """
        Simple query expansion for document search.

        Adds document-related terms to improve retrieval.

        Args:
            query: Original query
            intent: Intent classification

        Returns:
            Rewrite result with expanded query
        """
        entities = intent.get("entities", [])
        entity_str = " ".join(entities)

        # Add document-related terms
        doc_terms = ["document", "file", "report", "documentation"]
        expansion = " ".join(doc_terms)

        rewritten = f"{query} {entity_str} {expansion}".strip()

        return {
            "query": rewritten,
            "filters": {"source": "google_drive"},
            "strategy": "expansion",
        }

    async def _lightweight_rewrite(self, query: str, intent: dict) -> dict[str, Any]:
        """
        Minimal rewrite for general queries.

        Just passes through the original query.

        Args:
            query: Original query
            intent: Intent classification

        Returns:
            Passthrough result
        """
        return {"query": query, "filters": {}, "strategy": "passthrough"}

    def _format_history(self, history: list[dict]) -> str:
        """
        Format conversation history for context.

        Args:
            history: List of conversation messages

        Returns:
            Formatted history string
        """
        if not history:
            return "(No recent context)"

        formatted = []
        for msg in history[-3:]:  # Last 3 messages
            role = msg.get("role", "user")
            content = msg.get("content", "")[:200]  # Truncate long messages
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted)

    def get_stats(self) -> dict[str, Any]:
        """
        Get query rewriter statistics.

        Returns:
            Dictionary with rewriter status
        """
        return {
            "enabled": self.enable_rewriting,
            "strategies": ["hyde", "semantic", "expansion", "passthrough"],
            "synonym_categories": list(self.SEMANTIC_SYNONYMS.keys()),
        }
