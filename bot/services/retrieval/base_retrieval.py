"""
Base Retrieval Service

Contains shared functionality for all vector database retrieval implementations.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class BaseRetrieval:
    """Base class for vector database retrieval implementations"""

    def __init__(self, settings):
        self.settings = settings

    def _extract_entities_simple(self, query: str) -> set[str]:
        """
        Generic entity extraction: treat every significant word as an entity,
        just filter out common filler words.

        Args:
            query: User query text

        Returns:
            Set of entity terms (all significant words from query)
        """
        # Define comprehensive stop words to filter out
        stop_words = {
            # Articles, prepositions, conjunctions
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
            # Common verbs
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
            # Question words
            "what",
            "when",
            "where",
            "why",
            "how",
            "who",
            "which",
            "whose",
            # Pronouns
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
            # Common adjectives/adverbs
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
            # Modal verbs
            "can",
            "could",
            "will",
            "would",
            "should",
            "shall",
            "may",
            "might",
            "must",
            # Other common filler words
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
        }

        # Extract all words (2+ characters, alphanumeric)
        words = re.findall(r"\b[a-zA-Z0-9]{2,}\b", query.lower())

        # Filter out stop words and keep everything else as entities
        entities = {word for word in words if word not in stop_words}

        logger.debug(f"Extracted entities from '{query}': {entities}")
        return entities

    def _apply_entity_boosting(
        self, query: str, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Apply entity boosting to search results.

        Args:
            query: User query for entity extraction
            results: Search results to boost

        Returns:
            Results with entity boosting applied
        """
        try:
            # Extract entities from query
            entities = self._extract_entities_simple(query)
            logger.debug(f"🔍 Applying entity boosting for entities: {entities}")

            # Boost results that contain entities
            enhanced_results = []
            for result in results:
                content = result.get("content", "").lower()
                metadata = result.get("metadata", {})

                # Calculate entity boost
                entity_boost = 0.0
                matching_entities = 0

                for entity in entities:
                    if entity.lower() in content:
                        entity_boost += self.settings.rag.entity_content_boost
                        matching_entities += 1

                    # Check title/filename for entities
                    title = metadata.get("file_name", "").lower()
                    if entity.lower() in title:
                        entity_boost += self.settings.rag.entity_title_boost
                        matching_entities += 1

                # Apply boost to similarity score
                original_similarity = result.get("similarity", 0)
                boosted_similarity = min(1.0, original_similarity + entity_boost)

                # Add debug info
                result["_entity_boost"] = entity_boost
                result["_matching_entities"] = matching_entities
                result["_original_similarity"] = original_similarity
                result["similarity"] = boosted_similarity

                enhanced_results.append(result)

            # Sort by boosted similarity
            enhanced_results.sort(key=lambda x: x["similarity"], reverse=True)

            logger.debug(
                f"🎯 Entity boosting: {len(entities)} entities found, "
                f"boosted {sum(1 for r in enhanced_results if r['_entity_boost'] > 0)} results"
            )

            return enhanced_results

        except Exception as e:
            logger.error(f"Entity boosting failed: {e}")
            return results

    def _apply_diversification_strategy(
        self, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Apply smart similarity-first diversification with automatic document chunk limiting.

        For document chunks (has file_name), limits to max 3 chunks per document to avoid
        overwhelming context. For metric data (employees, projects - no file_name), returns
        pure similarity order.

        Args:
            results: Filtered results ready for diversification

        Returns:
            Diversified results
        """
        if not results:
            return []

        max_results = self.settings.rag.max_results

        # Smart diversification: limit chunks per document, pure similarity for metric data
        return self._smart_similarity_diversify(results, max_results)

    def _smart_similarity_diversify(
        self, results: list[dict[str, Any]], max_results: int
    ) -> list[dict[str, Any]]:
        """
        Smart similarity-first diversification.

        - For document chunks (has file_name): Limit to RAG_MAX_CHUNKS_PER_DOCUMENT per document
        - For metric data (no file_name): Pure similarity order

        Args:
            results: Input results sorted by similarity
            max_results: Maximum total results to return

        Returns:
            Diversified results
        """
        if not results:
            return []

        selected = []
        doc_chunk_count = {}  # Track chunks per document
        max_per_doc = self.settings.rag.max_chunks_per_document

        for result in results:
            if len(selected) >= max_results:
                break

            file_name = result.get("metadata", {}).get("file_name")

            # If it's a document chunk (has file_name), limit per document
            if file_name and file_name != "Unknown":
                count = doc_chunk_count.get(file_name, 0)
                if count >= max_per_doc:
                    continue
                doc_chunk_count[file_name] = count + 1

            # For metric data (no file_name) or under limit, add by similarity
            selected.append(result)

        logger.debug(
            f"Smart diversification: Selected {len(selected)} results "
            f"({len(doc_chunk_count)} unique documents, max {max_per_doc} chunks per doc)"
        )

        return selected

    def _diversify_document_first(
        self, results: list[dict[str, Any]], max_results: int, max_unique_docs: int
    ) -> list[dict[str, Any]]:
        """
        Document-first diversification: Get 1 chunk per document first, then fill remaining.

        Strategy:
        1. Get the best chunk from each unique document (up to max_unique_docs)
        2. If we have remaining slots, get additional chunks from those documents

        Args:
            results: Input results sorted by similarity
            max_results: Maximum total results to return
            max_unique_docs: Maximum unique documents to include

        Returns:
            Diversified results with document-first strategy
        """
        if not results:
            return []

        # Group by document
        docs_by_file = {}
        for result in results:
            file_name = result.get("metadata", {}).get("file_name", "Unknown")
            if file_name not in docs_by_file:
                docs_by_file[file_name] = []
            docs_by_file[file_name].append(result)

        # Sort chunks within each document by similarity (highest first)
        for _file_name, chunks in docs_by_file.items():
            chunks.sort(key=lambda x: x.get("similarity", 0), reverse=True)

        # Phase 1: Get 1 chunk per document (up to max_unique_docs)
        selected_results = []
        selected_docs = []

        # Sort documents by their best chunk similarity
        doc_items = list(docs_by_file.items())
        doc_items.sort(key=lambda x: x[1][0].get("similarity", 0), reverse=True)

        for file_name, chunks in doc_items[:max_unique_docs]:
            if len(selected_results) < max_results:
                selected_results.append(chunks[0])  # Best chunk from this document
                selected_docs.append(file_name)

        # Phase 2: Fill remaining slots with additional chunks from selected documents
        if len(selected_results) < max_results:
            for file_name in selected_docs:
                remaining_chunks = docs_by_file[file_name][
                    1:
                ]  # Skip first chunk (already added)
                for chunk in remaining_chunks:
                    if len(selected_results) >= max_results:
                        break
                    selected_results.append(chunk)
                if len(selected_results) >= max_results:
                    break

        logger.debug(
            f"Document-first diversification: Selected {len(selected_results)} chunks "
            f"from {len(selected_docs)} documents (max {max_unique_docs} docs, {max_results} total)"
        )

        return selected_results

    def _diversify_balanced(
        self, results: list[dict[str, Any]], max_results: int
    ) -> list[dict[str, Any]]:
        """
        Balanced round-robin diversification (existing algorithm).

        Args:
            results: Input results
            max_results: Maximum results to return

        Returns:
            Round-robin diversified results
        """
        if not results:
            return []

        # Group documents by file_name
        documents_by_file = {}
        for doc in results:
            file_name = doc.get("metadata", {}).get("file_name", "Unknown")
            if file_name not in documents_by_file:
                documents_by_file[file_name] = []
            documents_by_file[file_name].append(doc)

        # Sort chunks within each document by similarity (highest first)
        for _file_name, chunks in documents_by_file.items():
            chunks.sort(key=lambda x: x.get("similarity", 0), reverse=True)

        result = []
        file_names = list(documents_by_file.keys())

        # Round-robin through documents
        round_num = 0
        while len(result) < max_results and file_names:
            for file_name in file_names[:]:
                if len(result) >= max_results:
                    break

                if round_num < len(documents_by_file[file_name]):
                    result.append(documents_by_file[file_name][round_num])
                else:
                    file_names.remove(file_name)

            round_num += 1

        logger.debug(
            f"Balanced diversification: Selected {len(result)} chunks from {len(documents_by_file)} unique documents"
        )

        return result
