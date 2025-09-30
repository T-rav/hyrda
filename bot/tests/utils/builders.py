"""
Builder patterns for complex test objects

Provides fluent builder classes for creating complex test objects.
Builders are useful when objects have many optional parameters.
"""

from typing import Any


class MessageBuilder:
    """Builder for creating message objects with fluent API"""

    def __init__(self):
        self._role = "user"
        self._content = "Test message"
        self._name = None
        self._function_call = None

    def as_user(self):
        """Set role as user"""
        self._role = "user"
        return self

    def as_assistant(self):
        """Set role as assistant"""
        self._role = "assistant"
        return self

    def as_system(self):
        """Set role as system"""
        self._role = "system"
        return self

    def with_content(self, content: str):
        """Set message content"""
        self._content = content
        return self

    def with_name(self, name: str):
        """Set message name"""
        self._name = name
        return self

    def with_function_call(self, function_call: dict[str, Any]):
        """Set function call"""
        self._function_call = function_call
        return self

    def build(self) -> dict[str, Any]:
        """Build the message"""
        message = {
            "role": self._role,
            "content": self._content,
        }
        if self._name:
            message["name"] = self._name
        if self._function_call:
            message["function_call"] = self._function_call
        return message


class ConversationBuilder:
    """Builder for creating conversation histories"""

    def __init__(self):
        self._messages = []

    def add_user_message(self, content: str):
        """Add user message"""
        self._messages.append({"role": "user", "content": content})
        return self

    def add_assistant_message(self, content: str):
        """Add assistant message"""
        self._messages.append({"role": "assistant", "content": content})
        return self

    def add_system_message(self, content: str):
        """Add system message"""
        self._messages.append({"role": "system", "content": content})
        return self

    def add_message(self, role: str, content: str):
        """Add custom message"""
        self._messages.append({"role": role, "content": content})
        return self

    def add_messages(self, messages: list[dict[str, str]]):
        """Add multiple messages"""
        self._messages.extend(messages)
        return self

    def build(self) -> list[dict[str, str]]:
        """Build the conversation"""
        return self._messages.copy()


class SearchResultBuilder:
    """Builder for creating search results"""

    def __init__(self):
        self._id = "result-1"
        self._content = "Test content"
        self._similarity = 0.85
        self._metadata = {}

    def with_id(self, result_id: str):
        """Set result ID"""
        self._id = result_id
        return self

    def with_content(self, content: str):
        """Set content"""
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
        """Add title to metadata"""
        self._metadata["title"] = title
        return self

    def with_source(self, source: str):
        """Add source to metadata"""
        self._metadata["source"] = source
        return self

    def build(self) -> dict[str, Any]:
        """Build the search result"""
        return {
            "id": self._id,
            "content": self._content,
            "similarity": self._similarity,
            "metadata": self._metadata,
        }


class SearchResultsBuilder:
    """Builder for creating lists of search results"""

    def __init__(self):
        self._results = []

    def add_result(
        self,
        content: str,
        similarity: float = 0.85,
        metadata: dict[str, Any] | None = None,
    ):
        """Add a search result"""
        result = {
            "id": f"result-{len(self._results) + 1}",
            "content": content,
            "similarity": similarity,
            "metadata": metadata or {},
        }
        self._results.append(result)
        return self

    def add_results_with_similarity_range(
        self,
        count: int,
        content_prefix: str = "Content",
        similarity_range: tuple[float, float] = (0.7, 0.9),
    ):
        """Add multiple results with similarity in range"""
        sim_min, sim_max = similarity_range
        sim_step = (sim_max - sim_min) / (count - 1) if count > 1 else 0

        for i in range(count):
            similarity = sim_max - (i * sim_step)
            self.add_result(
                content=f"{content_prefix} {i + 1}",
                similarity=similarity,
            )
        return self

    def build(self) -> list[dict[str, Any]]:
        """Build the search results list"""
        return self._results.copy()


class ThreadHistoryBuilder:
    """Builder for creating Slack thread histories"""

    def __init__(self):
        self._messages = []
        self._next_ts = 1234567890.0

    def add_message(
        self,
        text: str,
        user: str = "U12345",
        ts: str | None = None,
        thread_ts: str | None = None,
    ):
        """Add message to thread"""
        if ts is None:
            ts = f"{self._next_ts:.6f}"
            self._next_ts += 1.0

        message = {
            "text": text,
            "user": user,
            "ts": ts,
        }

        if thread_ts:
            message["thread_ts"] = thread_ts

        self._messages.append(message)
        return self

    def add_bot_message(
        self,
        text: str,
        bot_id: str = "B12345678",
        ts: str | None = None,
    ):
        """Add bot message to thread"""
        if ts is None:
            ts = f"{self._next_ts:.6f}"
            self._next_ts += 1.0

        message = {
            "text": text,
            "bot_id": bot_id,
            "ts": ts,
            "subtype": "bot_message",
        }
        self._messages.append(message)
        return self

    def add_thread_reply(
        self,
        text: str,
        user: str = "U12345",
        thread_ts: str = "1234567890.000000",
    ):
        """Add reply to thread"""
        return self.add_message(text=text, user=user, thread_ts=thread_ts)

    def build(self) -> list[dict[str, Any]]:
        """Build the thread history"""
        return self._messages.copy()


class SlackFileBuilder:
    """Builder for creating Slack file objects"""

    def __init__(self):
        self._id = "F12345"
        self._name = "test.txt"
        self._mimetype = "text/plain"
        self._size = 1024
        self._url_private = "https://files.slack.com/test"
        self._content = None

    def with_id(self, file_id: str):
        """Set file ID"""
        self._id = file_id
        return self

    def with_name(self, name: str):
        """Set filename"""
        self._name = name
        return self

    def with_mimetype(self, mimetype: str):
        """Set MIME type"""
        self._mimetype = mimetype
        return self

    def as_pdf(self):
        """Configure as PDF file"""
        self._mimetype = "application/pdf"
        if not self._name.endswith(".pdf"):
            self._name = f"{self._name.rsplit('.', 1)[0]}.pdf"
        return self

    def as_text(self):
        """Configure as text file"""
        self._mimetype = "text/plain"
        if not self._name.endswith(".txt"):
            self._name = f"{self._name.rsplit('.', 1)[0]}.txt"
        return self

    def as_image(self):
        """Configure as image file"""
        self._mimetype = "image/png"
        if not self._name.endswith((".png", ".jpg", ".jpeg")):
            self._name = f"{self._name.rsplit('.', 1)[0]}.png"
        return self

    def with_size(self, size: int):
        """Set file size"""
        self._size = size
        return self

    def with_url(self, url: str):
        """Set file URL"""
        self._url_private = url
        return self

    def with_content(self, content: bytes):
        """Set file content"""
        self._content = content
        self._size = len(content)
        return self

    def build(self) -> dict[str, Any]:
        """Build the Slack file object"""
        file_obj = {
            "id": self._id,
            "name": self._name,
            "mimetype": self._mimetype,
            "size": self._size,
            "url_private": self._url_private,
        }
        if self._content:
            file_obj["content"] = self._content
        return file_obj
