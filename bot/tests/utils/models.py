"""
Model factory patterns for test data

Provides factories for creating various model objects used across tests.
Consolidates duplicate factory patterns from multiple test files.
"""

from datetime import datetime
from typing import Any

from models import RetrievalResult
from models.retrieval import RetrievalMethod


class MessageFactory:
    """Factory for creating test messages"""

    @staticmethod
    def create_user_message(content: str = "Hello") -> dict[str, str]:
        """Create user message"""
        return {"role": "user", "content": content}

    @staticmethod
    def create_assistant_message(content: str = "Hi there!") -> dict[str, str]:
        """Create assistant message"""
        return {"role": "assistant", "content": content}

    @staticmethod
    def create_system_message(
        content: str = "You are a helpful assistant",
    ) -> dict[str, str]:
        """Create system message"""
        return {"role": "system", "content": content}

    @staticmethod
    def create_conversation(
        user_msg: str = "Hello", assistant_msg: str = "Hi!"
    ) -> list[dict[str, str]]:
        """Create simple conversation"""
        return [
            MessageFactory.create_user_message(user_msg),
            MessageFactory.create_assistant_message(assistant_msg),
        ]

    @staticmethod
    def create_conversation_with_system(
        system_msg: str = "You are helpful",
        user_msg: str = "Hello",
        assistant_msg: str = "Hi!",
    ) -> list[dict[str, str]]:
        """Create conversation with system message"""
        return [
            MessageFactory.create_system_message(system_msg),
            MessageFactory.create_user_message(user_msg),
            MessageFactory.create_assistant_message(assistant_msg),
        ]


class SlackEventFactory:
    """Factory for creating Slack event objects"""

    @staticmethod
    def create_message_event(
        text: str = "Test message",
        user: str = "U12345",
        channel: str = "C12345",
        ts: str = "1234567890.123456",
    ) -> dict[str, Any]:
        """Create Slack message event"""
        return {
            "type": "message",
            "text": text,
            "user": user,
            "channel": channel,
            "ts": ts,
        }

    @staticmethod
    def create_app_mention_event(
        text: str = "Test mention",
        user: str = "U12345",
        channel: str = "C12345",
    ) -> dict[str, Any]:
        """Create Slack app mention event"""
        return {
            "type": "app_mention",
            "text": text,
            "user": user,
            "channel": channel,
        }

    @staticmethod
    def create_thread_reply_event(
        text: str = "Reply",
        user: str = "U12345",
        channel: str = "C12345",
        thread_ts: str = "1234567890.123456",
    ) -> dict[str, Any]:
        """Create Slack thread reply event"""
        return {
            "type": "message",
            "text": text,
            "user": user,
            "channel": channel,
            "thread_ts": thread_ts,
        }


class TextDataFactory:
    """Factory for creating text data for formatting tests"""

    @staticmethod
    def create_text_with_sources(
        content: str = "Here is some information.",
        sources: dict[str, str] | None = None,
    ) -> str:
        """Create text with source citations"""
        default_sources = {
            "Document 1": "https://example.com/doc1",
            "Document 2": "https://example.com/doc2",
        }
        sources_to_use = sources or default_sources

        sources_text = "\n".join(
            [f"[{title}]({url})" for title, url in sources_to_use.items()]
        )
        return f"{content}\n\nSources used:\n{sources_text}"

    @staticmethod
    def create_text_without_sources(content: str = "Simple text") -> str:
        """Create text without source citations"""
        return content

    @staticmethod
    def create_slack_formatted_sources(
        content: str = "Here is some information.",
        sources: dict[str, str] | None = None,
    ) -> str:
        """Create Slack-formatted text with sources"""
        default_sources = {
            "Document 1": "https://example.com/doc1",
            "Document 2": "https://example.com/doc2",
        }
        sources_to_use = sources or default_sources

        sources_text = "\n".join(
            [f"<{url}|{title}>" for title, url in sources_to_use.items()]
        )
        return f"{content}\n\nSources used:\n{sources_text}"

    @staticmethod
    def create_complex_message_text(
        code: str = "print('hello')",
        items: list[str] | None = None,
        sources: dict[str, str] | None = None,
    ) -> str:
        """Create complex message with code, lists, and sources"""
        default_items = ["Item 1", "Item 2", "Item 3"]
        items_to_use = items or default_items

        text = f"Here's some code:\n```python\n{code}\n```\n\n"
        text += "And a list:\n" + "\n".join([f"* {item}" for item in items_to_use])

        if sources:
            text += "\n\n" + TextDataFactory.create_text_with_sources("", sources)

        return text

    @staticmethod
    def create_formatted_complex_message(
        code: str = "print('hello')",
        items: list[str] | None = None,
        sources: dict[str, str] | None = None,
    ) -> str:
        """Create formatted complex message (expected output)"""
        default_items = ["Item 1", "Item 2", "Item 3"]
        items_to_use = items or default_items

        # After slackify-markdown processing
        text = f"Here's some code:\n```python\n{code}\n```\n\n"
        text += "And a list:\n" + "\n".join([f"* {item}" for item in items_to_use])

        if sources:
            text += "\n\n" + TextDataFactory.create_slack_formatted_sources("", sources)

        return text


class RetrievalResultFactory:
    """Factory for creating retrieval result objects"""

    @staticmethod
    def create_basic_result(
        content: str = "Test content",
        similarity: float = 0.9,
        source: RetrievalMethod = RetrievalMethod.DENSE,
    ) -> RetrievalResult:
        """Create basic retrieval result"""
        return RetrievalResult(
            content=content,
            similarity=similarity,
            chunk_id="chunk-1",
            document_id="doc-1",
            source=source,
            metadata={},
            retrieved_at=datetime.now(),
        )

    @staticmethod
    def create_results_list(
        count: int = 3,
        similarity_range: tuple[float, float] = (0.7, 0.9),
    ) -> list[RetrievalResult]:
        """Create list of retrieval results with varying similarity"""
        results = []
        sim_min, sim_max = similarity_range
        sim_step = (sim_max - sim_min) / (count - 1) if count > 1 else 0

        for i in range(count):
            similarity = sim_max - (i * sim_step)
            result = RetrievalResultFactory.create_basic_result(
                content=f"Content {i + 1}",
                similarity=similarity,
            )
            results.append(result)

        return results

    @staticmethod
    def create_dense_result(content: str = "Dense content") -> RetrievalResult:
        """Create dense retrieval result"""
        return RetrievalResultFactory.create_basic_result(
            content=content, source=RetrievalMethod.DENSE
        )

    @staticmethod
    def create_sparse_result(content: str = "Sparse content") -> RetrievalResult:
        """Create sparse retrieval result"""
        return RetrievalResultFactory.create_basic_result(
            content=content, source=RetrievalMethod.SPARSE
        )

    @staticmethod
    def create_hybrid_result(content: str = "Hybrid content") -> RetrievalResult:
        """Create hybrid retrieval result"""
        return RetrievalResultFactory.create_basic_result(
            content=content, source=RetrievalMethod.HYBRID
        )


class ContextChunkBuilder:
    """Builder for creating context chunks with metadata"""

    def __init__(self):
        self._content = "Default content"
        self._metadata = {}
        self._similarity = 0.85
        self._chunk_id = "chunk-1"
        self._document_id = "doc-1"

    def with_content(self, content: str):
        """Set chunk content"""
        self._content = content
        return self

    def with_similarity(self, similarity: float):
        """Set similarity score"""
        self._similarity = similarity
        return self

    def with_metadata(self, metadata: dict[str, Any]):
        """Set metadata"""
        self._metadata = metadata
        return self

    def with_title(self, title: str):
        """Set title in metadata"""
        self._metadata["title"] = title
        return self

    def with_filename(self, filename: str):
        """Set filename in metadata"""
        self._metadata["filename"] = filename
        return self

    def with_ids(self, chunk_id: str, document_id: str):
        """Set chunk and document IDs"""
        self._chunk_id = chunk_id
        self._document_id = document_id
        return self

    def build(self) -> dict[str, Any]:
        """Build the context chunk"""
        return {
            "id": self._chunk_id,
            "content": self._content,
            "similarity": self._similarity,
            "metadata": self._metadata,
            "document_id": self._document_id,
        }


class RetrievalResultBuilder:
    """Builder for creating retrieval results with fluent API"""

    def __init__(self):
        self._content = "Default content"
        self._similarity = 0.85
        self._chunk_id = "chunk-1"
        self._document_id = "doc-1"
        self._source = RetrievalMethod.DENSE
        self._metadata = {}
        self._rank = None
        self._rerank_score = None

    def with_content(self, content: str):
        """Set content"""
        self._content = content
        return self

    def with_similarity(self, similarity: float):
        """Set similarity score"""
        self._similarity = similarity
        return self

    def with_source(self, source: RetrievalMethod):
        """Set retrieval source"""
        self._source = source
        return self

    def with_ids(self, chunk_id: str, document_id: str):
        """Set IDs"""
        self._chunk_id = chunk_id
        self._document_id = document_id
        return self

    def with_metadata(self, metadata: dict[str, Any]):
        """Set metadata"""
        self._metadata = metadata
        return self

    def with_rank(self, rank: int):
        """Set rank"""
        self._rank = rank
        return self

    def with_rerank_score(self, score: float):
        """Set rerank score"""
        self._rerank_score = score
        return self

    def build(self) -> RetrievalResult:
        """Build the retrieval result"""
        return RetrievalResult(
            content=self._content,
            similarity=self._similarity,
            chunk_id=self._chunk_id,
            document_id=self._document_id,
            source=self._source,
            metadata=self._metadata,
            rank=self._rank,
            rerank_score=self._rerank_score,
            retrieved_at=datetime.now(),
        )
