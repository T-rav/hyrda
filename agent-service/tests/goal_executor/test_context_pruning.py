"""Tests for context pruning in goal executor.

Tests that tool results are properly pruned to manage context window size.
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agents.goal_executor.nodes.executor import (
    HARD_CLEAR_PLACEHOLDER,
    HARD_CLEAR_THRESHOLD,
    KEEP_LAST_TOOL_RESULTS,
    MIN_PRUNABLE_CHARS,
    SOFT_TRIM_THRESHOLD,
    _hard_clear_content,
    _is_image_content,
    _soft_trim_content,
    prune_tool_results,
)


class TestSoftTrimContent:
    """Tests for soft-trim content function."""

    def test_small_content_unchanged(self):
        """Content below threshold should not be trimmed."""
        content = "Small content"
        result = _soft_trim_content(content, threshold=1000)
        assert result == content

    def test_large_content_trimmed(self):
        """Content above threshold should have middle removed."""
        # Create content that exceeds threshold
        content = "A" * 60_000
        result = _soft_trim_content(content, threshold=50_000)

        # Should have head, ellipsis marker, and tail
        assert "characters trimmed" in result
        assert result.startswith("A" * 1000)  # Head preserved
        assert result.endswith("A" * 1000)  # Tail preserved
        assert len(result) < len(content)

    def test_preserves_head_and_tail(self):
        """Should preserve content from both ends."""
        content = "HEAD" + ("X" * 60_000) + "TAIL"
        result = _soft_trim_content(content, threshold=50_000)

        assert "HEAD" in result
        assert "TAIL" in result


class TestHardClearContent:
    """Tests for hard-clear content function."""

    def test_returns_placeholder_with_size(self):
        """Should return placeholder with original size."""
        content = "A" * 10_000
        result = _hard_clear_content(content)

        assert HARD_CLEAR_PLACEHOLDER in result
        assert "10,000" in result  # Size formatted with commas


class TestIsImageContent:
    """Tests for image content detection."""

    def test_detects_data_uri(self):
        """Should detect data:image URIs."""
        assert _is_image_content("data:image/png;base64,iVBOR...")

    def test_detects_png_base64(self):
        """Should detect PNG base64 signature."""
        assert _is_image_content("iVBORw0KGgoAAAANSUhEUg...")

    def test_detects_jpeg_base64(self):
        """Should detect JPEG base64 signature."""
        assert _is_image_content("/9j/4AAQSkZJRgABAQAA...")

    def test_detects_high_alnum_ratio(self):
        """Should detect base64-like content by character ratio and diversity."""
        # Create content that looks like base64 (mixed case, digits, high diversity)
        base64_chars = (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        )
        content = (base64_chars * 50)[:2000]  # Enough length with high diversity
        assert _is_image_content(content)

    def test_does_not_detect_repetitive_text(self):
        """Should not detect repetitive text as image content."""
        # Repetitive text has low character diversity
        content = "A" * 2000
        assert not _is_image_content(content)

    def test_normal_text_not_image(self):
        """Normal text should not be detected as image."""
        content = "This is normal text with spaces and punctuation!"
        assert not _is_image_content(content)


class TestPruneToolResults:
    """Tests for the main pruning function."""

    def test_empty_messages_unchanged(self):
        """Empty message list should be returned unchanged."""
        messages = []
        result = prune_tool_results(messages)
        assert result == []

    def test_no_tool_messages_unchanged(self):
        """Messages without tool results should be unchanged."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there"),
        ]
        result = prune_tool_results(messages)
        assert result == messages

    def test_small_tool_results_unchanged(self):
        """Small tool results should not be pruned."""
        messages = [
            HumanMessage(content="Search for something"),
            ToolMessage(content="Small result", tool_call_id="1"),
        ]
        result = prune_tool_results(messages)
        assert result[1].content == "Small result"

    def test_large_tool_result_soft_trimmed(self):
        """Large tool results should be soft-trimmed."""
        large_content = "A" * (SOFT_TRIM_THRESHOLD + 10_000)
        messages = [
            HumanMessage(content="Search"),
            ToolMessage(content=large_content, tool_call_id="1"),
            ToolMessage(content="recent", tool_call_id="2"),
            ToolMessage(content="recent", tool_call_id="3"),
            ToolMessage(content="recent", tool_call_id="4"),
        ]
        result = prune_tool_results(messages)

        # First tool message should be trimmed (not protected)
        assert "trimmed" in result[1].content
        # Recent ones should be unchanged
        assert result[2].content == "recent"

    def test_very_large_tool_result_hard_cleared(self):
        """Very large tool results should be hard-cleared."""
        huge_content = "A" * (HARD_CLEAR_THRESHOLD + 10_000)
        messages = [
            HumanMessage(content="Search"),
            ToolMessage(content=huge_content, tool_call_id="1"),
            ToolMessage(content="recent", tool_call_id="2"),
            ToolMessage(content="recent", tool_call_id="3"),
            ToolMessage(content="recent", tool_call_id="4"),
        ]
        result = prune_tool_results(messages)

        # First tool message should be cleared
        assert HARD_CLEAR_PLACEHOLDER in result[1].content

    def test_protects_last_n_results(self):
        """Should protect the last N tool results."""
        large_content = "A" * (SOFT_TRIM_THRESHOLD + 10_000)
        messages = [
            ToolMessage(content=large_content, tool_call_id="1"),
            ToolMessage(content=large_content, tool_call_id="2"),
            ToolMessage(content=large_content, tool_call_id="3"),
        ]

        # With keep_last=3, all should be protected
        result = prune_tool_results(messages, keep_last=3)
        for msg in result:
            assert "trimmed" not in msg.content

    def test_preserves_tool_call_id(self):
        """Pruned messages should preserve tool_call_id."""
        large_content = "A" * (SOFT_TRIM_THRESHOLD + 10_000)
        messages = [
            ToolMessage(content=large_content, tool_call_id="test-id-123"),
            ToolMessage(content="recent", tool_call_id="2"),
            ToolMessage(content="recent", tool_call_id="3"),
            ToolMessage(content="recent", tool_call_id="4"),
        ]
        result = prune_tool_results(messages)

        assert result[0].tool_call_id == "test-id-123"

    def test_skips_image_content(self):
        """Should not prune image content even if large."""
        # Large base64-like image content
        image_content = "data:image/png;base64," + ("ABCD1234" * 20_000)
        messages = [
            ToolMessage(content=image_content, tool_call_id="1"),
            ToolMessage(content="recent", tool_call_id="2"),
            ToolMessage(content="recent", tool_call_id="3"),
            ToolMessage(content="recent", tool_call_id="4"),
        ]
        result = prune_tool_results(messages, keep_last=1)

        # Image should not be pruned
        assert result[0].content == image_content

    def test_skips_below_min_prunable(self):
        """Should not prune results below minimum threshold."""
        content = "A" * (MIN_PRUNABLE_CHARS - 100)
        messages = [
            ToolMessage(content=content, tool_call_id="1"),
        ]
        result = prune_tool_results(messages, keep_last=0)

        # Should not be pruned
        assert result[0].content == content


class TestPruningThresholds:
    """Tests for pruning threshold constants."""

    def test_thresholds_are_ordered(self):
        """Thresholds should be in correct order."""
        assert MIN_PRUNABLE_CHARS < SOFT_TRIM_THRESHOLD < HARD_CLEAR_THRESHOLD

    def test_keep_last_is_reasonable(self):
        """Keep last should be a small positive number."""
        assert 1 <= KEEP_LAST_TOOL_RESULTS <= 10
