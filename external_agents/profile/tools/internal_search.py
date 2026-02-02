"""Internal search tool for querying the internal knowledge base.

A self-contained LangChain tool that performs deep research on the vector database
using only LangChain primitives - no bot services.
"""

import json
import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class InternalSearchInput(BaseModel):
    """Input schema for internal search tool."""

    query: str = Field(
        min_length=3,
        description="What to search for in internal knowledge base. Be specific about what you're looking for. MUST be a meaningful search query (minimum 3 characters). DO NOT call with empty string.",
    )
    effort: str = Field(
        default="medium",
        description='Research depth - "low" (2 queries), "medium" (3 queries), "high" (5 queries). Default: "medium"',
    )
    profile_type: str = Field(
        default="company",
        description='Type of profile being researched: "company" or "employee". Used to format output appropriately.',
    )


class InternalSearchTool(BaseTool):
    """Search the internal knowledge base (vector database) for existing information.

    Use this FIRST before web search to check if we already have information about:
    - Existing customers or past clients
    - Previous projects or engagements
    - Internal documentation
    - Historical company data

    This tool is self-contained and uses only LangChain primitives.
    """

    name: str = "internal_search_tool"
    description: str = (
        "Search the internal knowledge base for existing information. "
        "Use this FIRST before web search to check our internal docs, customer history, past projects, and internal documentation. "
        "IMPORTANT: Only call if you have a specific company name or topic to search for (minimum 3 characters). "
        "DO NOT call with empty query."
    )
    args_schema: type[BaseModel] = InternalSearchInput

    # LangChain components (injected at initialization)
    llm: Any = None  # LangChain ChatModel
    embeddings: Any = None  # LangChain Embeddings

    # Direct Qdrant client (production use - REQUIRED)
    qdrant_client: Any  # Direct Qdrant client (REQUIRED)
    vector_collection: str  # Qdrant collection name (REQUIRED)

    class Config:
        """Config class."""
        arbitrary_types_allowed = True

    def __init__(
        self,
        llm: Any = None,
        embeddings: Any = None,
        qdrant_client: Any = None,
        vector_collection: str = None,
        **kwargs,
    ):
        """Initialize with direct Qdrant client.

        Args:
            llm: LangChain ChatModel (e.g., ChatOpenAI, ChatAnthropic)
            embeddings: LangChain Embeddings (e.g., OpenAIEmbeddings)
            qdrant_client: Direct Qdrant client (REQUIRED)
            vector_collection: Qdrant collection name (REQUIRED)
            **kwargs: Additional BaseTool arguments
        """
        # If qdrant_client or vector_collection not provided, lazy-load from environment
        if qdrant_client is None or vector_collection is None:
            import os

            from qdrant_client import QdrantClient

            vector_host = os.getenv("VECTOR_HOST", "localhost")
            vector_port = os.getenv("VECTOR_PORT", "6333")
            vector_api_key = os.getenv("VECTOR_API_KEY")

            if qdrant_client is None:
                if vector_api_key:
                    qdrant_client = QdrantClient(
                        host=vector_host,
                        port=int(vector_port),
                        api_key=vector_api_key,
                        https=True,
                        verify=False,  # Accept self-signed certs in internal network
                    )
                else:
                    qdrant_client = QdrantClient(
                        host=vector_host,
                        port=int(vector_port),
                        https=True,
                        verify=False,  # Accept self-signed certs in internal network
                    )

            if vector_collection is None:
                vector_collection = os.getenv(
                    "VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base"
                )

        # Pass components as kwargs to avoid Pydantic issues
        kwargs["llm"] = llm
        kwargs["embeddings"] = embeddings
        kwargs["qdrant_client"] = qdrant_client
        kwargs["vector_collection"] = vector_collection

        super().__init__(**kwargs)

        # Lazy-load LLM/embeddings if not provided
        if not all([self.llm, self.embeddings]):
            self._initialize_components()

    def _initialize_components(self):
        """Initialize LangChain components from environment (fallback only).

        Uses environment variables matching .env file format.
        """
        try:
            import os

            # Get settings from environment (matching actual .env keys)
            llm_api_key = os.getenv("LLM_API_KEY")
            llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")

            embedding_api_key = os.getenv(
                "EMBEDDING_API_KEY", llm_api_key
            )  # Fallback to LLM key
            embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

            # Initialize LangChain LLM
            if not self.llm and llm_api_key:
                from langchain_openai import ChatOpenAI

                self.llm = ChatOpenAI(
                    model=llm_model,
                    api_key=llm_api_key,
                    temperature=0,
                )
                logger.info(f"Initialized LLM: {llm_model}")

            # Initialize LangChain Embeddings
            if not self.embeddings and embedding_api_key:
                from langchain_openai import OpenAIEmbeddings

                self.embeddings = OpenAIEmbeddings(
                    model=embedding_model,
                    api_key=embedding_api_key,
                )
                logger.info(f"Initialized embeddings: {embedding_model}")

            # Qdrant client is now initialized in __init__, so just log status
            if self.qdrant_client:
                logger.info(
                    f"Using Qdrant client for collection: {self.vector_collection}"
                )
            else:
                logger.warning(
                    "Qdrant client not initialized - internal search unavailable"
                )

        except Exception:
            logger.exception("Failed to initialize internal search components")
            logger.info("Internal search tool will be unavailable")

    async def _direct_qdrant_search(self, query: str, k: int = 100):
        """Search Qdrant directly without LangChain (preserves metadata).

        Args:
            query: Search query text
            k: Number of results to return

        Returns:
            List of tuples: [(doc_dict, score), ...]
            where doc_dict has 'page_content' and 'metadata' keys (LangChain-compatible format)
        """
        # If qdrant_client not initialized, return empty results
        if not self.qdrant_client:
            return []

        from dataclasses import dataclass

        # Simple doc class to match LangChain's Document interface
        @dataclass
        class SimpleDoc:
            """SimpleDoc class."""
            page_content: str
            metadata: dict

        # Get embedding for query
        from langchain_openai import OpenAIEmbeddings

        if isinstance(self.embeddings, OpenAIEmbeddings):
            query_vector = await self.embeddings.aembed_query(query)
        else:
            # Fallback for other embedding types
            query_vector = self.embeddings.embed_query(query)

        # Search Qdrant directly (using new query_points API)
        search_results = self.qdrant_client.query_points(
            collection_name=self.vector_collection,
            query=query_vector,
            limit=k,
            with_payload=True,
        ).points

        # Convert to LangChain-compatible format
        results = []
        for result in search_results:
            # Extract text content
            text = result.payload.get("text", "")

            # ALL other fields are metadata (source, file_name, chunk_id, etc.)
            metadata = {k: v for k, v in result.payload.items() if k != "text"}

            doc = SimpleDoc(page_content=text, metadata=metadata)
            score = result.score
            results.append((doc, score))

        return results

    async def _arun(
        self, query: str, effort: str = "medium", profile_type: str = "company"
    ) -> str:
        """Execute internal search asynchronously.

        Args:
            query: Search query
            effort: Research depth level
            profile_type: Type of profile ("company" or "employee")

        Returns:
            Formatted search results with citations
        """
        # Check if components are available
        if not all([self.qdrant_client, self.llm, self.embeddings]):
            return (
                "Internal search service not available (vector database not configured)"
            )

        try:
            logger.info(f"🔍 Internal search ({effort}): {query[:100]}...")

            # Determine number of sub-queries based on effort
            num_queries = {"low": 2, "medium": 3, "high": 5}.get(effort, 3)

            # Step 1: Decompose query into sub-queries
            sub_queries = await self._decompose_query(query, num_queries)
            logger.info(f"📋 Generated {len(sub_queries)} sub-queries: {sub_queries}")

            # Step 2: Retrieve context for each sub-query (SIMPLE direct search - no rewriting)
            all_docs = []
            seen_content = set()

            for idx, sub_query in enumerate(sub_queries, 1):
                logger.debug(f"Retrieving for sub-query {idx}/{len(sub_queries)}")

                # Direct search without rewriting (like regular RAG)
                # This ensures we find documents that actually mention the company name
                # Use direct Qdrant search to preserve metadata
                results = await self._direct_qdrant_search(
                    sub_query,  # Use original sub-query, not rewritten
                    k=100,  # Get many more results (Gemini 2.5 can handle large context)
                )

                logger.info(
                    f"   Sub-query '{sub_query}' returned {len(results)} results"
                )
                if results:
                    for i, (doc, score) in enumerate(results[:3], 1):
                        file_name = doc.metadata.get(
                            "file_name", doc.metadata.get("title", "unknown")
                        )
                        # Also show if content has company name for debugging
                        content_preview = doc.page_content[:150].replace("\n", " ")
                        logger.info(f"      {i}. {file_name} (score: {score:.4f})")
                        logger.debug(f"         Content: {content_preview}...")

                # Apply entity boosting (like regular RAG does)
                results = self._apply_entity_boosting(sub_query, results)

                # Deduplicate by content
                for doc, score in results:
                    content_key = doc.page_content[:100]  # First 100 chars as key
                    if content_key not in seen_content:
                        seen_content.add(content_key)
                        all_docs.append(
                            {
                                "content": doc.page_content,
                                "metadata": doc.metadata,
                                "score": score,
                                "sub_query": sub_query,
                            }
                        )

            # Fallback retrieval: if thin results, try targeted queries that MUST include company name
            try:
                has_case_study = any(
                    "case study"
                    in (d.get("metadata", {}).get("file_name", "") or "").lower()
                    or "case study" in (d.get("content", "") or "").lower()
                    for d in all_docs
                )
                # Extract probable company name from original query (between 'profile ' and ' and ' if present)
                company = None
                q_lower = query.lower()
                if q_lower.startswith("profile "):
                    after = q_lower[len("profile ") :]
                    if " and " in after:
                        company = after.split(" and ", 1)[0].strip()
                    else:
                        company = after.strip()
                if not company:
                    # fallback: first token
                    tokens = q_lower.split()
                    company = tokens[0] if tokens else None
                company = company.strip().strip("\"' ") if company else ""

                # CRITICAL: Only do fallback if we have a company name AND few results
                # Never search for generic "case study" without company name - causes false positives!
                if len(all_docs) < 5 and not has_case_study and company:
                    # Only search with company name included - prevents false positives
                    fallback_phrases = [
                        f"{company} case study",
                        f"{company} project",
                        f"{company} opm case study",
                        f"{company} engagement",
                        f"{company} client",
                    ]
                    for phrase in fallback_phrases:
                        try:
                            results = await self._direct_qdrant_search(
                                phrase,
                                k=5,
                            )
                            # CRITICAL: Filter results to only include docs that mention the company
                            # This prevents false positives from other companies' case studies
                            for doc, score in results:
                                content_lower = doc.page_content.lower()
                                file_name_lower = doc.metadata.get(
                                    "file_name", ""
                                ).lower()
                                # Only include if company name appears in content or filename
                                if (
                                    company in content_lower
                                    or company in file_name_lower
                                ):
                                    content_key = doc.page_content[:100]
                                    if content_key not in seen_content:
                                        seen_content.add(content_key)
                                        all_docs.append(
                                            {
                                                "content": doc.page_content,
                                                "metadata": doc.metadata,
                                                "score": score,
                                                "sub_query": f"fallback:{phrase}",
                                            }
                                        )
                                        logger.info(
                                            f"   Fallback match: {doc.metadata.get('file_name', 'unknown')} contains '{company}'"
                                        )
                        except Exception as _e:
                            logger.debug(
                                f"Fallback retrieval failed for '{phrase}': {_e}"
                            )
            except Exception as _e:
                logger.debug(f"Fallback planning failed: {_e}")

            # Step 3: Rank and limit
            all_docs.sort(key=lambda x: x["score"])  # Lower score = better in Qdrant
            # Increased limits for Gemini 2.5's large context (1M tokens)
            max_docs = {"low": 15, "medium": 30, "high": 50}.get(effort, 30)
            final_docs = all_docs[:max_docs]

            logger.info(f"📊 Found {len(final_docs)} unique documents")

            # Ensure metric/CRM evidence is included in final docs for relationship detection
            try:
                metric_doc = None
                for d in all_docs:
                    meta = d.get("metadata", {}) or {}
                    content_l = (d.get("content", "") or "").lower()
                    if (
                        str(meta.get("namespace", "")).lower() == "metric"
                        or str(meta.get("source", "")).lower() == "metric"
                        or str(meta.get("data_type", "")).lower() == "client"
                        or "client id:" in content_l
                    ):
                        metric_doc = d
                        break
                if metric_doc and metric_doc not in final_docs:
                    final_docs = (
                        [metric_doc] + final_docs[:-1]
                        if len(final_docs) >= max_docs
                        else [metric_doc] + final_docs
                    )
            except Exception as _e:
                logger.debug(f"Metric evidence inclusion failed: {_e}")

            # Step 4: Synthesize findings
            if not final_docs:
                return "**No relevant information found in internal knowledge base.**"

            summary = await self._synthesize_findings(
                query, final_docs, sub_queries, profile_type
            )

            # Step 5: Format results
            result_text = self._format_results(
                summary, final_docs, sub_queries, len(all_docs)
            )

            return result_text

        except Exception as e:
            logger.error(f"Internal search failed: {e}", exc_info=True)
            return f"Internal search error: {str(e)}"

    def _run(self, query: str, effort: str = "medium") -> str:
        """Sync wrapper - not implemented (use async version)."""
        return "Internal search requires async execution. Use ainvoke() instead."

    def _extract_entities_simple(self, query: str) -> set[str]:
        """Extract entities from query (same logic as RetrievalService)."""
        import re

        stop_words = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "what",
            "when",
            "where",
            "why",
            "how",
            "who",
            "which",
            "whose",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "them",
            "this",
            "that",
            "these",
            "those",
            "any",
            "some",
            "all",
            "many",
            "much",
            "more",
            "most",
            "very",
            "really",
            "quite",
            "can",
            "could",
            "will",
            "would",
            "should",
            "shall",
            "may",
            "might",
            "must",
            "there",
            "here",
            "then",
            "than",
            "so",
            "just",
            "only",
            "also",
            "even",
            "still",
            "profile",
            "their",
            "needs",  # Query-specific stop words
        }
        words = re.findall(r"\b[a-zA-Z0-9]{2,}\b", query.lower())
        entities = {word for word in words if word not in stop_words}
        logger.debug(f"Extracted entities from '{query}': {entities}")
        return entities

    def _apply_entity_boosting(self, query: str, results: list[tuple]) -> list[tuple]:
        """Apply entity boosting to search results with strong company name preference."""
        try:
            entities = self._extract_entities_simple(query)
            logger.debug(f"🔍 Applying entity boosting for entities: {entities}")

            # Extract company name from query (first entity that's not 'case'/'studies'/'project'/etc.)
            company_name = None
            for entity in entities:
                if entity not in {
                    "case",
                    "studies",
                    "study",
                    "project",
                    "projects",
                    "completed",
                    "technologies",
                    "used",
                    "profile",
                }:
                    company_name = entity
                    break

            enhanced_results = []
            for doc, score in results:
                content = doc.page_content.lower()
                metadata = doc.metadata
                title = metadata.get("file_name", "").lower()

                # FILTER OUT index/overview files - they contaminate results
                if any(
                    keyword in title or keyword in content[:200]
                    for keyword in [
                        "index",
                        "overview",
                        "start here",
                        "slide index",
                        "snapshots overview",
                    ]
                ):
                    # Penalize index files heavily
                    entity_boost = -0.5  # Much worse score
                    logger.debug(
                        f"   ❌ Penalizing index file: {metadata.get('file_name', 'unknown')}"
                    )
                else:
                    # Calculate entity boost (5% per content match, 10% per title match)
                    entity_boost = 0.0
                    matching_entities = 0

                    # STRONG boost if company name appears in content/title
                    if company_name:
                        if company_name in content:
                            entity_boost += (
                                0.20  # 20% boost for company name in content
                            )
                            matching_entities += 1
                        if company_name in title:
                            entity_boost += 0.30  # 30% boost for company name in title
                            matching_entities += 1

                    # Regular boost for other entities
                    for entity in entities:
                        if entity == company_name:
                            continue  # Already handled above
                        if entity in content:
                            entity_boost += 0.02  # Small boost for other terms
                        if entity in title:
                            entity_boost += 0.05  # Small boost for other terms

                # Apply boost to similarity score
                # Note: Qdrant scores are DISTANCES (lower=better), not similarities
                # So we SUBTRACT the boost to improve the score
                boosted_score = max(0.0, score - entity_boost)

                logger.debug(
                    f"   Entity boost for {metadata.get('file_name', 'unknown')}: {entity_boost:.3f} (original: {score:.4f}, boosted: {boosted_score:.4f})"
                )

                enhanced_results.append((doc, boosted_score))

            # Sort by boosted score (lower is better for distance)
            enhanced_results.sort(key=lambda x: x[1])

            logger.debug(
                f"🎯 Entity boosting: {len(entities)} entities found, "
                f"boosted {sum(1 for _, s in enhanced_results if s < results[enhanced_results.index((_, s))][1])} results"
            )

            return enhanced_results

        except Exception as e:
            logger.error(f"Entity boosting failed: {e}")
            return results

    async def _rewrite_query(self, sub_query: str, original_query: str) -> str:
        """Rewrite a sub-query to maximize retrieval from internal knowledge base.

        Transforms queries into search-optimized versions focused on internal
        information like past projects, clients, engagements, and documentation.

        Args:
            sub_query: The sub-query to rewrite
            original_query: Original user query for context

        Returns:
            Rewritten query optimized for internal knowledge retrieval
        """
        try:
            # Extract company/client names from original query to preserve them
            import re

            company_match = re.search(
                r"profile\s+([a-z0-9_\-]+)", original_query.lower()
            )
            company_name = company_match.group(1) if company_match else None

            prompt = f"""You are optimizing search queries for an INTERNAL knowledge base containing:
- Past client projects and engagements
- Historical project documentation
- Internal company information
- Previous work examples and case studies

Original context: "{original_query}"
Sub-query to rewrite: "{sub_query}"

**CRITICAL: If a company or client name is mentioned (like "{company_name}"), you MUST include it in the rewritten query.**

Rewrite the sub-query to:
1. **ALWAYS include the client/company name if present in the original context**
2. Be specific to INTERNAL information (past projects, clients, our work)
3. Use language that matches internal documentation style (case studies, project names, deliverables)
4. Focus on "what did we do" rather than "what should we do"
5. Keep it concise (1-2 sentences max)

Return ONLY the rewritten query, no explanation.

Examples:
Input original: "profile acme and their needs", sub-query: "organizational structure"
Output: "What past work did we do with Acme related to their organizational structure or leadership team?"

Input original: "profile techcorp", sub-query: "React projects"
Output: "What React projects or engagements did we complete for TechCorp?"

Input original: "fintech api work", sub-query: "API development"
Output: "What API development or integration work have we done for financial technology clients?"

Now rewrite: "{sub_query}"
"""

            response = await self.llm.ainvoke(prompt)
            rewritten = (
                response.content if hasattr(response, "content") else str(response)
            )

            # Fallback to original if rewriting fails or returns empty
            return rewritten.strip() if rewritten.strip() else sub_query

        except Exception as e:
            logger.debug(f"Query rewriting failed, using original: {e}")
            return sub_query

    async def _decompose_query(self, query: str, num_queries: int) -> list[str]:
        """Decompose complex query into focused sub-queries using LLM.

        Args:
            query: Original query
            num_queries: Number of sub-queries to generate

        Returns:
            List of sub-queries
        """
        # Extract company name if present
        import re

        company_match = re.search(r"profile\s+([a-z0-9_\-]+)", query.lower())
        company_name = company_match.group(1) if company_match else None

        prompt = f"""You are a research query planner for searching an internal knowledge base containing past client projects, case studies, and engagements.

Original Query: "{query}"

**CRITICAL: If a company/client name is mentioned (like "{company_name}"), EVERY sub-query MUST include that name.**

Generate {num_queries} DISTINCT search queries that:
1. **ALWAYS include the company/client name if present** - this is mandatory!
2. Each query explores a DIFFERENT aspect: projects, case studies, technologies used, outcomes, team members
3. Use simple, direct language that matches how case studies and project docs are written
4. Focus on finding evidence of past work, not future plans

Examples:
Input: "profile acme corp and their needs"
Output: ["acme case study", "acme projects completed", "acme client engagement"]

Input: "profile techstart"
Output: ["techstart case study", "techstart project deliverables", "techstart past work"]

Format your response as a JSON array of strings:
["sub-query 1", "sub-query 2", ..., "sub-query {num_queries}"]

Return ONLY the JSON array, no explanation."""

        try:
            response = await self.llm.ainvoke(prompt)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )
            content = content.strip()

            # Try to extract JSON from markdown code blocks if present
            json_match = re.search(
                r"```(?:json)?\s*(\[.*?\])\s*```", content, re.DOTALL
            )
            if json_match:
                content = json_match.group(1)

            # Remove any leading/trailing text before/after the JSON array
            array_match = re.search(r"(\[.*\])", content, re.DOTALL)
            if array_match:
                content = array_match.group(1)

            sub_queries = json.loads(content)

            if isinstance(sub_queries, list) and len(sub_queries) > 0:
                return sub_queries
            else:
                logger.warning(f"Invalid sub-query format, using original: {content}")
                return [query]

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse sub-queries ({e}), using original query")
            return [query]
        except Exception as e:
            logger.error(f"Query decomposition failed: {e}")
            return [query]

    async def _synthesize_findings(
        self,
        query: str,
        docs: list[dict],
        sub_queries: list[str],
        profile_type: str = "company",
    ) -> str:
        """Synthesize findings into a summary using LLM.

        Args:
            query: Original query
            docs: Retrieved documents
            sub_queries: Sub-queries used
            profile_type: Type of profile ("company" or "employee")

        Returns:
            Synthesized summary
        """
        if not docs:
            return "No relevant information found."

        # Build context from top documents
        import re as _re

        def _extract_file_name(doc_dict: dict) -> str:
            meta = doc_dict.get("metadata", {}) or {}
            for key in ("file_name", "name", "title", "full_path"):
                val = meta.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            content_text = doc_dict.get("content", "") or ""
            m = _re.search(r"\[FILENAME\]\s*(.*?)\s*\[/FILENAME\]", content_text)
            return m.group(1).strip() if m else "unknown"

        context_parts = []
        evidence_corpus = []
        for idx, doc in enumerate(docs[:8], 1):
            file_name = _extract_file_name(doc)
            content = doc.get("content", "") or ""
            excerpt = content[:1000]
            context_parts.append(f"[Source {idx}: {file_name}]\n{excerpt}")
            if file_name and file_name != "unknown":
                evidence_corpus.append(file_name)
            if content:
                evidence_corpus.append(content)

        context = "\n\n".join(context_parts)

        # Generate synthesis with explicit relationship flags
        # CRITICAL: Extract company name to verify it's actually mentioned
        company_name = None
        q_lower = query.lower()
        if q_lower.startswith("profile "):
            after = q_lower[len("profile ") :]
            if " and " in after:
                company_name = after.split(" and ", 1)[0].strip()
            else:
                company_name = after.strip()
        if not company_name:
            # Extract multi-word company names by removing common query terms
            # This handles queries like "Baker College existing client relationship"
            # Stop words that typically appear after company name in search queries
            stop_words = {
                "existing",
                "client",
                "relationship",
                "projects",
                "case",
                "studies",
                "study",
                "engagement",
                "work",
                "history",
                "past",
                "previous",
                "information",
                "about",
                "details",
                "background",
                "overview",
                "profile",
                "company",
                "research",
            }
            tokens = q_lower.split()
            company_tokens = []
            for token in tokens:
                clean_token = token.strip("\"'(),.:;")
                if clean_token in stop_words:
                    break  # Stop at first stop word
                company_tokens.append(clean_token)

            company_name = " ".join(company_tokens) if company_tokens else None
        company_name = company_name.strip().strip("\"' ") if company_name else ""

        blob = "\n".join(evidence_corpus).lower()

        # CRITICAL: First check if company name is actually mentioned in the evidence
        # If company not mentioned, cannot have relationship evidence (prevents false positives)
        company_mentioned = company_name and company_name in blob

        signals = [
            "case study",
            "client engagement",
            "project delivered",
            "retrospective",
            "project summary",
            "partner hub",
            "approached us",
            "partnered with us",
            "we introduced",
            "we built",
            "opm case study",
            # metric/CRM textual patterns
            "client id:",
            "record_type: client",
        ]
        matched = [s for s in signals if s in blob]

        # CRITICAL: Check if company name appears in same document as relationship signals
        # This prevents false positives where company is mentioned in one doc but case studies are in another
        company_with_signals = False
        if company_mentioned and matched:
            # Check each document to see if it contains BOTH company name AND relationship signals
            for doc in docs[:5]:  # Check top 5 docs
                doc_text = (doc.get("content", "") or "").lower()
                doc_filename = (
                    doc.get("metadata", {}).get("file_name", "") or ""
                ).lower()
                doc_combined = doc_text + " " + doc_filename

                # Check if this doc has company name
                if company_name in doc_combined:
                    # Check if this same doc has relationship signals
                    has_signal = any(signal in doc_combined for signal in signals)
                    if has_signal:
                        company_with_signals = True
                        culprit_metadata = doc.get("metadata", {})
                        logger.warning(
                            f"🚨 CULPRIT FOUND: '{company_name}' + signals | "
                            f"file_name='{culprit_metadata.get('file_name', 'MISSING')}' | "
                            f"Full metadata: {culprit_metadata}"
                        )
                        break

        # Relationship evidence ONLY if: (1) signals present AND (2) company name mentioned AND (3) they appear together
        relationship_evidence = (
            bool(matched) and company_mentioned and company_with_signals
        )

        if matched and company_mentioned and not company_with_signals:
            logger.warning(
                f"Found relationship signals {matched} AND '{company_name}' mentioned, but NOT in same documents - marking as NO relationship to prevent false positive"
            )
        elif matched and not company_mentioned:
            logger.warning(
                f"Found relationship signals {matched} but company '{company_name}' not mentioned - marking as NO relationship to prevent false positive"
            )
        # Treat metric/CRM records as relationship evidence (ONLY if company name is in the same document)
        try:
            for d in docs:
                meta = d.get("metadata", {}) or {}
                meta_values = " ".join(str(v).lower() for v in meta.values())
                doc_content = (d.get("content", "") or "").lower()
                doc_combined = doc_content + " " + meta_values

                has_metric_record = (
                    "metric" in meta_values
                    or "record_type: client" in meta_values
                    or str(meta.get("record_type", "")).lower() == "client"
                )

                # CRITICAL: Only set relationship_evidence = True if company name appears in THIS document
                if has_metric_record:
                    if company_name and company_name in doc_combined:
                        relationship_evidence = True
                        if "metric record" not in matched:
                            matched.append("metric record")
                        logger.warning(
                            f"🚨 METRIC RECORD MATCH: '{company_name}' found in metric/CRM record | "
                            f"file_name='{meta.get('file_name', 'MISSING')}'"
                        )
                        break
                    else:
                        logger.debug(
                            f"Ignoring metric record without company name '{company_name}' | "
                            f"file_name='{meta.get('file_name', 'MISSING')}'"
                        )
        except Exception as e:
            logger.debug(f"Failed to check metric/CRM records: {e}")

        # Generate synthesis with profile-type specific prompts
        if profile_type == "employee":
            # EMPLOYEE/PERSON synthesis - return projects, skills, role info
            prompt = f"""You are a research synthesizer reviewing 8th Light's internal knowledge base for information about a person.

Research Query: "{query}"

Sub-queries explored:
{chr(10).join(f"{i}. {sq}" for i, sq in enumerate(sub_queries, 1))}

Retrieved Context:
{context}

Provide a well-structured answer focusing on:
1. **Projects**: What 8th Light projects has this person worked on? (client names, project names, roles, dates if available)
2. **Skills & Technologies**: What technologies, frameworks, or methodologies have they used?
3. **Role & Expertise**: What is their role/title? What are they known for professionally?
4. **Collaborations**: Who have they worked with? (8th Light team members, clients)
5. **Current Status**: Any information about their current work or focus areas?

If no information is found, simply state: "No 8th Light project records found for this person."

Keep your response focused and informative (2-3 paragraphs)."""
        else:
            # COMPANY synthesis - return relationship status (existing behavior)
            prompt = f"""You are a research synthesizer reviewing 8th Light's internal knowledge base.

**CRITICAL RELATIONSHIP RULES (STRICT)**
- Relationship evidence means any signal of past project work (e.g., filenames or content mentioning "Case Study", "client engagement", "project delivered", "retrospective", "project summary", "Partner Hub", "approached us", "partnered with us", "we introduced", "we built").
- If relationship_evidence is TRUE, you MUST state clearly that the company IS an existing client and list projects with details if available.
- If relationship_evidence is FALSE (documents are purely research/analysis), you MUST state there is no prior engagement.

Research Query: "{query}"

Sub-queries explored:
{chr(10).join(f"{i}. {sq}" for i, sq in enumerate(sub_queries, 1))}

Relationship Evidence Flags:
- relationship_evidence: {str(relationship_evidence).upper()}
- evidence_signals: {", ".join(matched) if matched else "none"}

Retrieved Context:
{context}

Provide a well-structured, comprehensive answer that:
1. The FIRST LINE MUST be an explicit "Relationship status" line:
   - "Relationship status: Existing client" when relationship_evidence is TRUE
   - "Relationship status: No prior engagement" when relationship_evidence is FALSE
2. If relationship exists: Summarize specific projects (what/when/tech) from the context
3. Synthesizes the most important findings and insights
4. Notes any gaps or areas with limited information

Keep your response focused and informative (2-3 paragraphs)."""

        try:
            response = await self.llm.ainvoke(prompt)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )
            content = content or "Unable to synthesize findings."

            # For employee profiles, return content as-is (no relationship status prefix)
            if profile_type == "employee":
                return content

            # For company profiles, add relationship status prefix
            # Deterministic prefix: Relationship status and optional project bullets
            status = (
                "Relationship status: Existing client"
                if relationship_evidence
                else "Relationship status: No prior engagement"
            )
            # Simple project cue extraction
            project_terms = [
                ("Partner Hub", "Partner Hub application"),
                ("archa", "Archa platform"),
                ("terraform", "Terraform/IaC"),
                ("aws", "AWS infrastructure"),
                ("analytics", "Analytics pipeline"),
                ("enrollment", "Enrollment platform"),
                ("crm", "CRM modernization"),
            ]
            bullets = []
            if relationship_evidence:
                bblob = blob
                for kw, label in project_terms:
                    if kw in bblob and label not in bullets:
                        bullets.append(f"- {label}")
            prefix = status
            if bullets:
                prefix += "\n\n" + "\n".join(bullets)
            # If content doesn't already start with status, prefix it
            normalized = content.strip().lower()
            if not normalized.startswith("relationship status:"):
                content = f"{prefix}\n\n" + content
            return content
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            if profile_type == "employee":
                return "No 8th Light project records found for this person."
            return "Relationship status: No prior engagement\n\nError synthesizing findings."

    def _format_results(
        self,
        summary: str,
        docs: list[dict],
        sub_queries: list[str],
        total_retrieved: int,
    ) -> str:
        """Format search results for presentation.

        Args:
            summary: Synthesized summary
            docs: Final documents
            sub_queries: Sub-queries used
            total_retrieved: Total documents retrieved

        Returns:
            Formatted result string
        """
        result_text = f"# Internal Knowledge Base Search\n\n{summary}\n\n"

        # Add document citations
        unique_files = len(
            {doc.get("metadata", {}).get("file_name", "unknown") for doc in docs}
        )

        result_text += (
            f"**Found in {unique_files} internal documents ({len(docs)} sections):**\n"
        )

        # List unique documents with relevance scores
        files_seen = set()
        source_index = 1
        for doc in docs[:10]:
            meta = doc.get("metadata", {}) or {}
            file_name = (
                meta.get("file_name")
                or meta.get("name")
                or meta.get("title")
                or meta.get("full_path")
                or ""
            )
            if not file_name:
                import re as _re2

                m = _re2.search(
                    r"\[FILENAME\]\s*(.*?)\s*\[/FILENAME\]",
                    doc.get("content", "") or "",
                )
                file_name = m.group(1).strip() if m else "unknown"
            # Provide readable name for metric records
            if file_name == "unknown" and (
                str(meta.get("namespace", "")).lower() == "metric"
                or str(meta.get("source", "")).lower() == "metric"
            ):
                client_name = (
                    meta.get("name")
                    or meta.get("client_name")
                    or "Metric Client Record"
                )
                file_name = f"Metric: {client_name}"
            web_view_link = doc.get("metadata", {}).get(
                "web_view_link", "internal://knowledge-base"
            )
            if file_name not in files_seen:
                files_seen.add(file_name)
                # Include "Internal search" keyword so this gets tagged as [INTERNAL_KB] downstream
                result_text += f"{source_index}. {web_view_link} - Internal search result: {file_name}\n"
                source_index += 1

        return result_text


# Factory function for easy instantiation
def internal_search_tool(
    llm: Any = None,
    embeddings: Any = None,
    qdrant_client: Any = None,
    vector_collection: str | None = None,
) -> InternalSearchTool | None:
    """Create an internal search tool instance.

    Args:
        llm: Optional LangChain ChatModel (will be lazy-loaded if not provided)
        embeddings: Optional LangChain Embeddings (will be lazy-loaded if not provided)
        qdrant_client: Direct Qdrant client (REQUIRED for production use)
        vector_collection: Qdrant collection name (REQUIRED for production use)

    Returns:
        Configured InternalSearchTool or None if unavailable
    """
    try:
        # Require both qdrant_client and vector_collection or neither (for lazy-loading from env)
        if qdrant_client and not vector_collection:
            vector_collection = "documents"  # Default collection name

        return InternalSearchTool(
            llm=llm,
            embeddings=embeddings,
            qdrant_client=qdrant_client,
            vector_collection=vector_collection,
        )
    except Exception as e:
        logger.error(f"Failed to create internal search tool: {e}")
        return None
