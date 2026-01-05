"""Tests for format_research_context source consolidation."""

import pytest

from agents.profiler.utils import format_research_context


@pytest.mark.asyncio
async def test_consolidates_sources_from_multiple_notes():
    """Test that sources from multiple notes are consolidated with global numbering."""

    # Create test notes with local citations
    note1 = """
This is finding 1 with citation [1] and another [2].

### Sources
1. https://example.com/article1 - Article 1
2. https://example.com/article2 - Article 2
"""

    note2 = """
This is finding 2 with citation [1] and [2] and [3].

### Sources
1. https://example.com/article3 - Article 3
2. https://example.com/article1 - Article 1 (duplicate)
3. https://example.com/article4 - Article 4
"""

    note3 = """
This is finding 3 with citation [1].

### Sources
1. https://example.com/article5 - Article 5
"""

    research_brief = "Test brief"
    notes = [note1, note2, note3]

    result = await format_research_context(research_brief, notes, "company")

    # Verify consolidated sources section exists
    assert "CONSOLIDATED SOURCE LIST" in result
    assert "Total sources available: 5" in result

    # Verify all unique sources are listed
    assert "1. https://example.com/article1 - Article 1" in result
    assert "2. https://example.com/article2 - Article 2" in result
    assert "3. https://example.com/article3 - Article 3" in result
    assert "4. https://example.com/article4 - Article 4" in result
    assert "5. https://example.com/article5 - Article 5" in result

    # Verify citations were renumbered in note content
    # Note 1: [1] -> [1], [2] -> [2] (no change)
    assert "This is finding 1 with citation [1] and another [2]" in result

    # Note 2: [1] -> [3], [2] -> [1] (article1 is global #1), [3] -> [4]
    assert "This is finding 2 with citation [3] and [1] and [4]" in result

    # Note 3: [1] -> [5]
    assert "This is finding 3 with citation [5]" in result


@pytest.mark.asyncio
async def test_handles_notes_without_sources():
    """Test that notes without sources section are handled gracefully."""

    note1 = "Finding without sources section."
    note2 = """
Finding with sources [1].

### Sources
1. https://example.com/test
"""

    research_brief = "Test brief"
    notes = [note1, note2]

    result = await format_research_context(research_brief, notes, "company")

    # Should still work
    assert "Finding without sources section" in result
    assert "Finding with sources [1]" in result
    assert "CONSOLIDATED SOURCE LIST" in result
    assert "Total sources available: 1" in result


@pytest.mark.asyncio
async def test_handles_empty_notes():
    """Test that empty notes list is handled gracefully."""

    research_brief = "Test brief"
    notes = []

    result = await format_research_context(research_brief, notes, "company")

    # Should not crash
    assert "Profile Research Context" in result
    assert "**Research Findings** (0 sections):" in result
    assert "CONSOLIDATED SOURCE LIST" not in result


@pytest.mark.asyncio
async def test_deduplicates_sources_by_url():
    """Test that duplicate URLs are deduplicated."""

    note1 = """
Content with [1] and [2].

### Sources
1. https://example.com/same
2. https://example.com/different1
"""

    note2 = """
More content with [1] and [2].

### Sources
1. https://example.com/same
2. https://example.com/different2
"""

    research_brief = "Test brief"
    notes = [note1, note2]

    result = await format_research_context(research_brief, notes, "company")

    # Should have 3 unique sources, not 4
    assert "Total sources available: 3" in result

    # Verify deduplication: second note's [1] should map to global [1]
    # Note 2: [1] -> [1] (same URL), [2] -> [3]
    assert "More content with [1] and [3]" in result


@pytest.mark.asyncio
async def test_preserves_source_descriptions():
    """Test that source descriptions are preserved."""

    note = """
Content [1].

### Sources
1. https://example.com/article - This is a detailed description of the article
"""

    research_brief = "Test brief"
    notes = [note]

    result = await format_research_context(research_brief, notes, "company")

    assert (
        "https://example.com/article - This is a detailed description of the article"
        in result
    )


@pytest.mark.asyncio
async def test_handles_sources_without_descriptions():
    """Test sources that don't have descriptions."""

    note = """
Content [1].

### Sources
1. https://example.com/article
"""

    research_brief = "Test brief"
    notes = [note]

    result = await format_research_context(research_brief, notes, "company")

    assert "1. https://example.com/article\n" in result


@pytest.mark.asyncio
async def test_provides_guidance_to_llm():
    """Test that the output includes guidance for the LLM."""

    note = """
Content [1] and [2].

### Sources
1. https://example.com/source1
2. https://example.com/source2
"""

    research_brief = "Test brief"
    notes = [note]

    result = await format_research_context(research_brief, notes, "company")

    # Should provide clear guidance
    assert "use these citation numbers in your report" in result
    assert "ensure your ## Sources section lists ALL 2 sources" in result
    assert "[1] through [2]" in result
