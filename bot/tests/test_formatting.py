import os
import sys

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.formatting import MessageFormatter


# TDD Factory Patterns for Message Formatting Testing
class TextDataFactory:
    """Factory for creating different types of text data for testing"""

    @staticmethod
    def create_code_block_text(
        code: str = "print('hello world')", language: str = "python"
    ) -> str:
        """Create text with code blocks"""
        return f"Try this code:\n```{language}\n{code}\n```"

    @staticmethod
    def create_formatted_code_block_text(code: str = "print('hello world')") -> str:
        """Create expected formatted code block text"""
        return f"Try this code:\n```\n{code}\n```"

    @staticmethod
    def create_bullet_point_text(
        items: list[str] | None = None, intro: str = "Here's a list:"
    ) -> str:
        """Create text with bullet points"""
        if items is None:
            items = ["Item 1", "Item 2"]
        bullet_text = "\n".join(f"* {item}" for item in items)
        return f"{intro}\n{bullet_text}"

    @staticmethod
    def create_formatted_bullet_point_text(
        items: list[str] | None = None, intro: str = "Here's a list:"
    ) -> str:
        """Create expected formatted bullet point text"""
        if items is None:
            items = ["Item 1", "Item 2"]
        bullet_text = "\n".join(f"•   {item}" for item in items)
        return f"{intro}\n{bullet_text}"

    @staticmethod
    def create_text_with_sources(
        content: str = "Here's some information.",
        sources: dict[str, str] | None = None,
    ) -> str:
        """Create text with source citations"""
        if sources is None:
            sources = {
                "Document 1": "http://example.com/doc1",
                "Document 2": "http://example.com/doc2",
            }
        source_links = "\n".join(f"[{name}]({url})" for name, url in sources.items())
        return f"{content}\n\nSources used:\n{source_links}"

    @staticmethod
    def create_slack_formatted_sources(
        content: str = "Here's some information.",
        sources: dict[str, str] | None = None,
    ) -> str:
        """Create expected Slack-formatted source citations"""
        if sources is None:
            sources = {
                "Document 1": "http://example.com/doc1",
                "Document 2": "http://example.com/doc2",
            }
        source_links = "\n".join(f"<{url}|{name}>" for name, url in sources.items())
        return f"{content}\n\nSources used:\n{source_links}"

    @staticmethod
    def create_text_without_sources(
        content: str = "Here's some information without sources.",
    ) -> str:
        """Create text without source citations"""
        return content

    @staticmethod
    def create_complex_message_text(
        code: str = "print('hello')",
        items: list[str] | None = None,
        sources: dict[str, str] | None = None,
    ) -> str:
        """Create complex message with code, bullets, and sources"""
        if items is None:
            items = ["Item 1", "Item 2"]
        if sources is None:
            sources = {"Document": "http://example.com"}

        code_section = f"Here's some code:\n```python\n{code}\n```"
        bullet_section = "\n\nAnd a list:\n" + "\n".join(f"* {item}" for item in items)
        source_section = "\n\nSources used:\n" + "\n".join(
            f"[{name}]({url})" for name, url in sources.items()
        )

        return code_section + bullet_section + source_section

    @staticmethod
    def create_formatted_complex_message(
        code: str = "print('hello')",
        items: list[str] | None = None,
        sources: dict[str, str] | None = None,
    ) -> str:
        """Create expected formatted complex message"""
        if items is None:
            items = ["Item 1", "Item 2"]
        if sources is None:
            sources = {"Document": "http://example.com"}

        code_section = f"Here's some code:\n```\n{code}\n```"
        bullet_section = "\nAnd a list:\n" + "\n".join(f"•   {item}" for item in items)
        source_section = "\nSources used:\n" + "\n".join(
            f"<{url}|{name}>" for name, url in sources.items()
        )

        return code_section + bullet_section + source_section


class TestMessageFormatter:
    """Tests for the MessageFormatter class using factory patterns"""

    @pytest.mark.asyncio
    async def test_format_code_blocks(self):
        """Test formatting of code blocks"""
        input_text = TextDataFactory.create_code_block_text()
        expected = TextDataFactory.create_formatted_code_block_text()

        result = MessageFormatter.format_code_blocks(input_text)
        assert result == expected

    @pytest.mark.asyncio
    async def test_format_code_blocks_custom(self):
        """Test formatting of code blocks with custom content"""
        custom_code = "def hello():\n    return 'world'"
        input_text = TextDataFactory.create_code_block_text(
            code=custom_code, language="python"
        )
        expected = TextDataFactory.create_formatted_code_block_text(code=custom_code)

        result = MessageFormatter.format_code_blocks(input_text)
        assert result == expected

    @pytest.mark.asyncio
    async def test_format_bullet_points(self):
        """Test formatting of bullet points"""
        input_text = TextDataFactory.create_bullet_point_text()
        expected = TextDataFactory.create_formatted_bullet_point_text()

        result = MessageFormatter.format_bullet_points(input_text)
        assert result == expected

    @pytest.mark.asyncio
    async def test_format_bullet_points_custom_items(self):
        """Test formatting of bullet points with custom items"""
        custom_items = ["Feature A", "Feature B", "Feature C"]
        input_text = TextDataFactory.create_bullet_point_text(
            items=custom_items, intro="Features:"
        )
        expected = TextDataFactory.create_formatted_bullet_point_text(
            items=custom_items, intro="Features:"
        )

        result = MessageFormatter.format_bullet_points(input_text)
        assert result == expected

    @pytest.mark.asyncio
    async def test_format_for_slack_with_sources(self):
        """Test formatting of source citations"""
        input_text = TextDataFactory.create_text_with_sources()
        expected = TextDataFactory.create_slack_formatted_sources()

        result = await MessageFormatter.format_for_slack(input_text)
        assert result == expected

    @pytest.mark.asyncio
    async def test_format_for_slack_with_custom_sources(self):
        """Test formatting of source citations with custom sources"""
        custom_sources = {
            "API Documentation": "https://api.example.com/docs",
            "User Guide": "https://guide.example.com",
        }
        input_text = TextDataFactory.create_text_with_sources(
            content="Check these resources.", sources=custom_sources
        )
        expected = TextDataFactory.create_slack_formatted_sources(
            content="Check these resources.", sources=custom_sources
        )

        result = await MessageFormatter.format_for_slack(input_text)
        assert result == expected

    @pytest.mark.asyncio
    async def test_format_for_slack_without_sources(self):
        """Test formatting of text without sources"""
        input_text = TextDataFactory.create_text_without_sources()
        expected = input_text  # Should be unchanged

        result = await MessageFormatter.format_for_slack(input_text)
        assert result == expected

    @pytest.mark.asyncio
    async def test_format_message_complete(self):
        """Test complete message formatting pipeline"""
        input_text = TextDataFactory.create_complex_message_text()
        expected = TextDataFactory.create_formatted_complex_message()

        result = await MessageFormatter.format_message(input_text)
        assert result == expected

    @pytest.mark.asyncio
    async def test_format_message_with_custom_complex_content(self):
        """Test complete message formatting with custom content"""
        custom_code = "async def process():\n    await task()"
        custom_items = ["Task 1", "Task 2"]
        custom_sources = {"Process Guide": "https://process.example.com"}

        input_text = TextDataFactory.create_complex_message_text(
            code=custom_code, items=custom_items, sources=custom_sources
        )
        expected = TextDataFactory.create_formatted_complex_message(
            code=custom_code, items=custom_items, sources=custom_sources
        )

        result = await MessageFormatter.format_message(input_text)
        assert result == expected
