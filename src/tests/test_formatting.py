import sys
import os
import pytest
import asyncio

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.formatting import MessageFormatter


class TestMessageFormatter:
    """Tests for the MessageFormatter class"""

    @pytest.mark.asyncio
    async def test_format_code_blocks(self):
        """Test formatting of code blocks"""
        # Test input with language specified
        input_text = "Try this code:\n```python\nprint('hello world')\n```"
        expected = "Try this code:\n```\nprint('hello world')\n```"
        
        result = MessageFormatter.format_code_blocks(input_text)
        assert result == expected
        
    @pytest.mark.asyncio
    async def test_format_bullet_points(self):
        """Test formatting of bullet points"""
        input_text = "Here's a list:\n* Item 1\n* Item 2"
        expected = "Here's a list:\n• Item 1\n• Item 2"
        
        result = MessageFormatter.format_bullet_points(input_text)
        assert result == expected
        
    @pytest.mark.asyncio
    async def test_format_for_slack_with_sources(self):
        """Test formatting of source citations"""
        input_text = "Here's some information.\n\nSources used:\n[Document 1](http://example.com/doc1)\n[Document 2](http://example.com/doc2)"
        expected = "Here's some information.\n\nSources used:\n<http://example.com/doc1|Document 1>\n<http://example.com/doc2|Document 2>"
        
        result = await MessageFormatter.format_for_slack(input_text)
        assert result == expected
        
    @pytest.mark.asyncio
    async def test_format_for_slack_without_sources(self):
        """Test formatting of text without sources"""
        input_text = "Here's some information without sources."
        expected = input_text  # Should be unchanged
        
        result = await MessageFormatter.format_for_slack(input_text)
        assert result == expected
        
    @pytest.mark.asyncio
    async def test_format_message_complete(self):
        """Test complete message formatting pipeline"""
        input_text = "Here's some code:\n```python\nprint('hello')\n```\n\nAnd a list:\n* Item 1\n* Item 2\n\nSources used:\n[Document](http://example.com)"
        expected = "Here's some code:\n```\nprint('hello')\n```\n\nAnd a list:\n• Item 1\n• Item 2\n\nSources used:\n<http://example.com|Document>"
        
        result = await MessageFormatter.format_message(input_text)
        assert result == expected 