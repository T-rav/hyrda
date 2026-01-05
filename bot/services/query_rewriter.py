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

from services.langfuse_service import observe

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

    @observe(as_type="generation", name="query_rewriting")
    async def rewrite_query(
        self,
        query: str,
        conversation_history: list[dict] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Rewrite query using adaptive strategy based on intent.

        Args:
            query: Original user query
            conversation_history: Recent conversation messages for context
            user_id: Slack user ID for resolving "me/I" references

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
            # Get user context if user_id provided
            user_context = None
            if user_id:
                user_context = self._get_user_context(user_id)

            # Step 1: Classify query intent
            intent = await self._classify_intent(
                query, conversation_history or [], user_context
            )

            logger.info(
                f"Query intent: {intent.get('type')} (confidence: {intent.get('confidence', 0):.2f})"
            )

            # Step 2: Apply appropriate strategy
            if (
                intent["type"] == "team_allocation"
                and intent.get("confidence", 0) > 0.7
            ):
                result = await self._hyde_rewrite(query, intent, user_context)
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

    def _get_user_context(self, user_id: str) -> dict | None:
        """
        Get user context for resolving "me/I" references.

        Args:
            user_id: Slack user ID

        Returns:
            Dictionary with user info or None
        """
        try:
            from services.user_service import get_user_service

            user_service = get_user_service()
            user_info = user_service.get_user_info(user_id)

            if user_info:
                logger.info(
                    f"User context loaded: {user_info.get('real_name') or user_info.get('display_name', 'Unknown')}"
                )
                return user_info
        except Exception as e:
            logger.warning(f"Failed to get user context: {e}")

        return None

    @observe(as_type="generation", name="intent_classification")
    async def _classify_intent(
        self, query: str, conversation_history: list[dict], user_context: dict | None
    ) -> dict[str, Any]:
        """
        Classify query intent to determine rewriting strategy.

        Args:
            query: User query
            conversation_history: Recent conversation context
            user_context: User information for resolving "me/I" references

        Returns:
            Dictionary with intent classification
        """
        # Format recent conversation history (last 3 messages)
        history_context = self._format_history(conversation_history[-3:])

        # Format user context
        user_context_str = ""
        if user_context:
            # Use real_name from Slack (this is the formal full name)
            name = user_context.get("real_name") or user_context.get(
                "display_name", "Unknown"
            )
            email = user_context.get("email_address", "")
            user_context_str = f"\n\nCurrent User:\n- Name: {name}\n- Email: {email}\n- When the query contains 'me', 'I', 'my', or 'mine', this refers to {name}"

        logger.info(
            f"🔍 Classifying intent for query: '{query}' with history: {history_context[:200]}"
        )

        prompt = f"""Classify the intent of this user query to optimize information retrieval.

Query: "{query}"

Recent conversation context:
{history_context}{user_context_str}

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
1. Use "team_allocation" for queries about people on projects (e.g., "who worked on X", "engineers on Y", "which people worked on them")
2. Extract entities: project names, client names, person names mentioned in query OR conversation history
3. IMPORTANT: Resolve pronouns (them, it, that, those) using conversation context - extract the actual entity names from history
4. Infer time ranges from phrases like "in 2023", "last year", "currently"
5. Set confidence based on how clearly the query matches an intent type
6. Return ONLY valid JSON, no explanation

Examples:
Query: "who were the engineers on Ticketmaster projects?"
{{"type": "team_allocation", "entities": ["Ticketmaster"], "time_range": {{"start": null, "end": null}}, "confidence": 0.95}}

Query: "show me the architecture diagram for the API"
{{"type": "document_search", "entities": ["API", "architecture"], "time_range": {{"start": null, "end": null}}, "confidence": 0.9}}

Query: "what is the status of project X?"
{{"type": "project_info", "entities": ["project X"], "time_range": {{"start": null, "end": null}}, "confidence": 0.85}}

FOLLOW-UP QUESTION EXAMPLE:
Previous context: "RecoveryOne and 3Step projects used React"
Query: "which people worked on them?"
{{"type": "team_allocation", "entities": ["RecoveryOne", "3Step"], "time_range": {{"start": null, "end": null}}, "confidence": 0.9}}

Now classify this query. Return ONLY the JSON object:"""

        response = await self.llm_service.get_response(
            messages=[{"role": "user", "content": prompt}]
        )

        # Handle None response from LLM (e.g., API errors)
        if response is None:
            logger.warning("LLM returned None response for intent classification")
            return {
                "type": "general",
                "entities": [],
                "time_range": {"start": None, "end": None},
                "confidence": 0.3,
            }

        try:
            # Try to parse JSON from response
            intent = json.loads(response.strip())
            logger.info(
                f"✅ Intent classified as '{intent.get('type')}' with entities: {intent.get('entities')} (confidence: {intent.get('confidence', 0):.2f})"
            )
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

    @observe(as_type="generation", name="hyde_rewrite")
    async def _hyde_rewrite(
        self, query: str, intent: dict, user_context: dict | None = None
    ) -> dict[str, Any]:
        """
        HyDE (Hypothetical Document Embeddings) rewrite for team allocation queries.

        Generates a hypothetical employee record that would answer the query,
        then searches for employee records similar to this hypothetical one.

        Args:
            query: Original query
            intent: Intent classification
            user_context: User information for resolving "me/I" references

        Returns:
            Rewrite result with hypothetical employee record
        """
        entities = intent.get("entities", [])
        entity_context = f" for {entities[0]}" if entities else ""

        # Check if query refers to the current user
        refers_to_user = user_context and any(
            word in query.lower() for word in ["i", "me", "my", "mine"]
        )

        # Build prompt with user-specific template if applicable
        if refers_to_user:
            user_name = user_context.get("real_name") or user_context.get(
                "display_name", ""
            )
            user_email = user_context.get("email_address", "")

            prompt = f"""Generate a sample employee record for {user_name} that would answer: "{query}"

Create a realistic employee record for this specific person{entity_context}. Format it EXACTLY like this:

Employee: {user_name}
Email: {user_email}
Status: Allocated
Started: [start date]
Ended: [end date or Active]
Project History: [Project Name 1], [Project Name 2], [Project Name 3]

Fill in the dates and project history with realistic details that would match this person's background."""
        else:
            prompt = f"""Generate a sample employee record that would answer: "{query}"

Create a realistic employee record{entity_context}. Format it like this:

Employee: [Full Name]
Email: [email@company.com]
Status: Allocated
Started: [start date]
Ended: [end date or Active]
Project History: [Project Name 1], [Project Name 2], [Project Name 3]

Make it specific to the query context. Use realistic names, dates, and project names."""

        hypothetical_doc = await self.llm_service.get_response(
            messages=[{"role": "user", "content": prompt}]
        )

        # Handle None response from LLM
        if hypothetical_doc is None:
            logger.warning(
                "LLM returned None for HyDE generation, using original query"
            )
            return {"query": query, "filters": {}, "strategy": "passthrough"}

        return {
            "query": hypothetical_doc.strip(),
            "filters": {"record_type": "employee"},
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
