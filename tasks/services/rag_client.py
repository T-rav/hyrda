"""HTTP client for calling rag-service to ingest documents."""

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RAGIngestClient:
    """Client for calling rag-service HTTP API for document ingestion."""

    def __init__(self, base_url: str, service_token: str):
        """Initialize RAG ingest client.

        Args:
            base_url: Base URL of rag-service (e.g., http://localhost:8002)
            service_token: Service authentication token
        """
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.timeout = httpx.Timeout(300.0, connect=10.0)  # 5 minutes for ingestion

    async def ingest_documents(
        self, documents: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Ingest documents into RAG system via rag-service API.

        Args:
            documents: List of documents with 'content' and 'metadata'
                      [{
                          "content": "document text...",
                          "metadata": {"source": "...", "title": "..."}
                      }]

        Returns:
            Dict with ingestion results:
            {
                "success_count": 10,
                "error_count": 0,
                "status": "success"
            }
        """
        url = f"{self.base_url}/api/v1/ingest"

        headers = {
            "X-Service-Token": self.service_token,
            "Content-Type": "application/json",
        }

        payload = {"documents": documents}

        logger.info(
            f"Ingesting {len(documents)} documents to RAG service: {self.base_url}"
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url, content=json.dumps(payload), headers=headers
                )

                if response.status_code == 401:
                    raise RAGIngestError(
                        "Authentication failed - check service token"
                    )

                if response.status_code == 404:
                    # /api/v1/ingest endpoint doesn't exist - try calling vector service directly
                    logger.warning(
                        "RAG service /api/v1/ingest not found, falling back to direct vector ingestion"
                    )
                    return await self._ingest_direct(documents)

                if response.status_code != 200:
                    raise RAGIngestError(
                        f"RAG service failed: {response.status_code} - {response.text}"
                    )

                result = response.json()
                logger.info(
                    f"Ingestion complete: {result.get('success_count', 0)} success, "
                    f"{result.get('error_count', 0)} errors"
                )

                return result

        except httpx.TimeoutException as e:
            logger.error(f"RAG service timeout: {e}")
            raise RAGIngestError("RAG service timeout") from e

        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to RAG service: {e}")
            # Fall back to direct ingestion
            logger.info("Falling back to direct vector database ingestion")
            return await self._ingest_direct(documents)

        except Exception as e:
            logger.error(f"Error calling RAG service: {e}", exc_info=True)
            raise RAGIngestError(f"RAG service error: {str(e)}") from e

    async def _ingest_direct(
        self, documents: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Fall back to direct vector database ingestion.

        Args:
            documents: List of documents to ingest

        Returns:
            Dict with ingestion results
        """
        logger.info("Using direct vector database ingestion as fallback")

        try:
            # Import directly from tasks services
            from services.openai_embeddings import OpenAIEmbeddings
            from services.qdrant_client import QdrantClient

            # Initialize clients
            qdrant_client = QdrantClient()
            embeddings = OpenAIEmbeddings()

            success_count = 0
            error_count = 0

            for doc in documents:
                try:
                    content = doc.get("content", "")
                    metadata = doc.get("metadata", {})

                    if not content.strip():
                        logger.warning("Skipping document with empty content")
                        error_count += 1
                        continue

                    # Generate embedding
                    embedding = await embeddings.get_embedding(content)

                    # Add to Qdrant
                    await qdrant_client.add_documents(
                        texts=[content], embeddings=[embedding], metadata=[metadata]
                    )

                    success_count += 1

                except Exception as e:
                    logger.error(f"Error ingesting document: {e}")
                    error_count += 1

            return {
                "success_count": success_count,
                "error_count": error_count,
                "status": "success" if error_count == 0 else "partial",
            }

        except Exception as e:
            logger.error(f"Direct ingestion failed: {e}")
            raise RAGIngestError(f"Direct ingestion error: {str(e)}") from e


class RAGIngestError(Exception):
    """Exception raised when RAG ingestion operations fail."""

    pass
