"""
Configuration for ingestion script

Reads settings from environment variables without dependencies on bot/tasks config.
"""

import os
from dataclasses import dataclass


@dataclass
class VectorConfig:
    """Vector database configuration"""

    provider: str
    host: str
    port: int
    api_key: str | None
    collection_name: str

    @classmethod
    def from_env(cls):
        return cls(
            provider=os.getenv("VECTOR_PROVIDER", "qdrant"),
            host=os.getenv("VECTOR_HOST", "localhost"),
            port=int(os.getenv("VECTOR_PORT", "6333")),
            api_key=os.getenv("VECTOR_API_KEY"),
            collection_name=os.getenv(
                "VECTOR_COLLECTION_NAME", "insightmesh-knowledge-base"
            ),
        )


@dataclass
class EmbeddingConfig:
    """Embedding service configuration"""

    provider: str
    model: str
    api_key: str | None
    chunk_size: int
    chunk_overlap: int

    @classmethod
    def from_env(cls):
        return cls(
            provider=os.getenv("EMBEDDING_PROVIDER", "openai"),
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            api_key=os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY"),
            chunk_size=int(os.getenv("EMBEDDING_CHUNK_SIZE", "1000")),
            chunk_overlap=int(os.getenv("EMBEDDING_CHUNK_OVERLAP", "200")),
        )


@dataclass
class LLMConfig:
    """LLM service configuration"""

    provider: str
    api_key: str
    model: str
    base_url: str | None
    temperature: float
    max_tokens: int

    @classmethod
    def from_env(cls):
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            api_key=os.getenv("LLM_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            base_url=os.getenv("LLM_BASE_URL"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
        )


@dataclass
class RAGConfig:
    """RAG configuration"""

    enable_contextual_retrieval: bool

    @classmethod
    def from_env(cls):
        return cls(
            enable_contextual_retrieval=os.getenv(
                "RAG_ENABLE_CONTEXTUAL_RETRIEVAL", "false"
            ).lower()
            == "true",
        )
