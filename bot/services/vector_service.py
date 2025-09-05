"""
Vector database service for RAG functionality
"""

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Any

from config.settings import VectorSettings

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """Abstract base class for vector stores"""

    def __init__(self, settings: VectorSettings):
        self.settings = settings
        self.collection_name = settings.collection_name

    @abstractmethod
    async def initialize(self):
        """Initialize the vector store"""
        pass

    @abstractmethod
    async def add_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ):
        """Add documents to the vector store"""
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        similarity_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Search for similar documents"""
        pass

    @abstractmethod
    async def delete_documents(self, document_ids: list[str]):
        """Delete documents from the vector store"""
        pass

    @abstractmethod
    async def close(self):
        """Clean up resources"""
        pass


class ChromaVectorStore(VectorStore):
    """ChromaDB vector store implementation"""

    def __init__(self, settings: VectorSettings):
        super().__init__(settings)
        self.client = None
        self.collection = None

    async def initialize(self):
        """Initialize ChromaDB client and collection"""
        try:
            import chromadb  # noqa: PLC0415
            from chromadb.config import Settings as ChromaSettings  # noqa: PLC0415

            # Parse URL to determine if it's HTTP or persistent
            if self.settings.url.startswith("http"):
                # HTTP client
                host, port = (
                    self.settings.url.replace("http://", "")
                    .replace("https://", "")
                    .split(":")
                )
                self.client = chromadb.HttpClient(host=host, port=int(port))
            else:
                # Persistent client
                self.client = chromadb.PersistentClient(
                    path=self.settings.url,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )

            # Get or create collection
            if self.client is None:
                raise RuntimeError("ChromaDB client not initialized")
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name, metadata={"hnsw:space": "cosine"}
            )

            logger.info(f"ChromaDB initialized with collection: {self.collection_name}")

        except ImportError:
            raise ImportError(
                "chromadb package not installed. Run: pip install chromadb"
            ) from None
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    async def add_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ):
        """Add documents to ChromaDB"""
        try:
            # Generate IDs based on content hash
            document_ids = []
            for i, text in enumerate(texts):
                text_hash = hashlib.md5(
                    text.encode(), usedforsecurity=False
                ).hexdigest()
                document_ids.append(f"doc_{text_hash}_{i}")

            # Prepare metadata
            if metadata is None:
                metadata = [{"text": text} for text in texts]

            # Add to collection
            if self.collection is None:
                raise RuntimeError("ChromaDB collection not initialized")
            self.collection.add(
                documents=texts,
                embeddings=embeddings,
                metadatas=metadata,
                ids=document_ids,
            )

            logger.info(f"Added {len(texts)} documents to ChromaDB")

        except Exception as e:
            logger.error(f"Failed to add documents to ChromaDB: {e}")
            raise

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        similarity_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Search ChromaDB for similar documents"""
        try:
            if self.collection is None:
                raise RuntimeError("ChromaDB collection not initialized")
            results = self.collection.query(
                query_embeddings=[query_embedding], n_results=limit
            )

            # Format results
            documents = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    distance = (
                        results["distances"][0][i] if results.get("distances") else 0
                    )
                    similarity = 1 - distance  # Convert distance to similarity

                    if similarity >= similarity_threshold:
                        documents.append(
                            {
                                "content": doc,
                                "similarity": similarity,
                                "metadata": (
                                    results["metadatas"][0][i]
                                    if results.get("metadatas")
                                    else {}
                                ),
                                "id": (
                                    results["ids"][0][i]
                                    if results.get("ids")
                                    else f"doc_{i}"
                                ),
                            }
                        )

            logger.info(
                f"Found {len(documents)} documents above similarity threshold {similarity_threshold}"
            )
            return documents

        except Exception as e:
            logger.error(f"Failed to search ChromaDB: {e}")
            return []

    async def delete_documents(self, document_ids: list[str]):
        """Delete documents from ChromaDB"""
        try:
            if self.collection is None:
                raise RuntimeError("ChromaDB collection not initialized")
            self.collection.delete(ids=document_ids)
            logger.info(f"Deleted {len(document_ids)} documents from ChromaDB")
        except Exception as e:
            logger.error(f"Failed to delete documents from ChromaDB: {e}")

    async def close(self):
        """Clean up ChromaDB resources"""
        # ChromaDB doesn't require explicit cleanup
        pass


class PineconeVectorStore(VectorStore):
    """Pinecone vector store implementation"""

    def __init__(self, settings: VectorSettings):
        super().__init__(settings)
        self.index = None

    async def initialize(self):
        """Initialize Pinecone client and index"""
        try:
            from pinecone import Pinecone  # noqa: PLC0415

            if not self.settings.api_key:
                raise ValueError("Pinecone API key is required")

            # Initialize Pinecone client (v3.x API)
            pc = Pinecone(api_key=self.settings.api_key.get_secret_value())

            # Connect to existing index
            self.index = pc.Index(self.collection_name)

            logger.info(f"Pinecone initialized with index: {self.collection_name}")

        except ImportError:
            raise ImportError(
                "pinecone package not installed. Run: pip install pinecone"
            ) from None
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to initialize Pinecone: {e}")
            logger.error(
                f"Debug info - API key provided: {'Yes' if self.settings.api_key else 'No'}"
            )
            logger.error(
                f"Debug info - Environment provided: {'Yes' if self.settings.environment else 'No'}"
            )
            logger.error(f"Debug info - Index name: '{self.collection_name}'")
            logger.error(f"Debug info - Error type: {type(e).__name__}")

            # Provide helpful guidance based on error
            if "index" in error_msg.lower() and (
                "not found" in error_msg.lower()
                or "does not exist" in error_msg.lower()
            ):
                logger.error(
                    f"→ The Pinecone index '{self.collection_name}' does not exist."
                )
                logger.error(
                    "→ Please create this index in your Pinecone console first."
                )
            elif "api key" in error_msg.lower() or "unauthorized" in error_msg.lower():
                logger.error("→ Invalid or missing Pinecone API key.")
                logger.error("→ Check your VECTOR_API_KEY environment variable.")
            elif "environment" in error_msg.lower() or not self.settings.environment:
                logger.error("→ Pinecone environment not specified or invalid.")
                logger.error(
                    "→ For Pinecone v2.2.4, you need to set VECTOR_ENVIRONMENT (e.g., us-east-1-aws)"
                )
                logger.error(
                    "→ Check your Pinecone console for the correct environment name."
                )
            else:
                logger.error(
                    "→ Check your Pinecone configuration (API key, index name, environment)."
                )

            raise

    async def add_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ):
        """Add documents to Pinecone"""
        try:
            vectors = []
            for i, (text, embedding) in enumerate(zip(texts, embeddings, strict=False)):
                text_hash = hashlib.md5(
                    text.encode(), usedforsecurity=False
                ).hexdigest()
                doc_id = f"doc_{text_hash}_{i}"

                doc_metadata = metadata[i] if metadata else {}
                doc_metadata["text"] = text  # Store text in metadata

                vectors.append(
                    {"id": doc_id, "values": embedding, "metadata": doc_metadata}
                )

            # Upsert in batches
            if self.index is None:
                raise RuntimeError("Pinecone index not initialized")
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                await asyncio.get_event_loop().run_in_executor(
                    None, self.index.upsert, batch
                )

            logger.info(f"Added {len(texts)} documents to Pinecone")

        except Exception as e:
            logger.error(f"Failed to add documents to Pinecone: {e}")
            raise

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        similarity_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Search Pinecone for similar documents"""
        try:
            if self.index is None:
                raise RuntimeError("Pinecone index not initialized")
            # Run query in executor to avoid blocking
            query_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.index.query(
                    vector=query_embedding,
                    top_k=limit,
                    include_metadata=True,
                    include_values=False,
                ),
            )

            documents = []
            for match in query_result.matches:
                if match.score >= similarity_threshold:
                    documents.append(
                        {
                            "content": match.metadata.get("text", ""),
                            "similarity": match.score,
                            "metadata": match.metadata,
                            "id": match.id,
                        }
                    )

            logger.info(
                f"Found {len(documents)} documents above similarity threshold {similarity_threshold}"
            )
            return documents

        except Exception as e:
            logger.error(f"Failed to search Pinecone: {e}")
            logger.error(
                f"Debug info - Index initialized: {'Yes' if self.index else 'No'}"
            )
            logger.error(f"Debug info - Collection name: '{self.collection_name}'")

            if "connect" in str(e).lower():
                logger.error(
                    "→ Connection failed - check if Pinecone index exists and API credentials are correct"
                )
            elif "index" in str(e).lower():
                logger.error(
                    f"→ Index '{self.collection_name}' issue - verify it exists in Pinecone console"
                )

            return []

    async def delete_documents(self, document_ids: list[str]):
        """Delete documents from Pinecone"""
        try:
            if self.index is None:
                raise RuntimeError("Pinecone index not initialized")
            await asyncio.get_event_loop().run_in_executor(
                None, self.index.delete, document_ids
            )
            logger.info(f"Deleted {len(document_ids)} documents from Pinecone")
        except Exception as e:
            logger.error(f"Failed to delete documents from Pinecone: {e}")

    async def close(self):
        """Clean up Pinecone resources"""
        # Pinecone doesn't require explicit cleanup
        pass


def create_vector_store(settings: VectorSettings) -> VectorStore:
    """Factory function to create the appropriate vector store"""
    store_map = {
        "chroma": ChromaVectorStore,
        "pinecone": PineconeVectorStore,
    }

    store_class = store_map.get(settings.provider.lower())
    if not store_class:
        raise ValueError(f"Unsupported vector store provider: {settings.provider}")

    return store_class(settings)
