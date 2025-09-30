"""
TextDataFactory for test utilities
"""


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
