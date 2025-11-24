"""
Service Protocols for Better Abstraction

Defines interfaces for all services to enable proper dependency injection
and improve testability through interface segregation.
"""

from .langfuse import LangfuseServiceProtocol
from .llm import LLMServiceProtocol
from .metrics import MetricsServiceProtocol
from .rag import RAGServiceProtocol
from .slack import SlackServiceProtocol
from .vector import VectorServiceProtocol

__all__ = [
    "LLMServiceProtocol",
    "RAGServiceProtocol",
    "VectorServiceProtocol",
    "MetricsServiceProtocol",
    "LangfuseServiceProtocol",
    "SlackServiceProtocol",
]
