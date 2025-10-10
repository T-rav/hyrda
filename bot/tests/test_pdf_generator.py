"""Unit tests for PDF generation utility."""

from utils.pdf_generator import get_pdf_filename, markdown_to_pdf


class TestPDFFilename:
    """Tests for PDF filename generation."""

    def test_get_pdf_filename_basic(self):
        """Test basic filename generation."""
        filename = get_pdf_filename("test_report")
        assert filename.endswith(".pdf")
        assert "test_report" in filename
        assert len(filename) < 100  # Reasonable length

    def test_get_pdf_filename_with_profile_type(self):
        """Test filename generation with profile type."""
        filename = get_pdf_filename("Tesla Motors Profile", profile_type="company")
        assert "company" in filename
        assert "tesla" in filename.lower() or "Tesla" in filename
        assert filename.endswith(".pdf")

    def test_get_pdf_filename_sanitization(self):
        """Test filename sanitization of special characters."""
        filename = get_pdf_filename(
            "Report with spaces & special!@# chars?", profile_type="test"
        )
        assert "/" not in filename
        assert "@" not in filename
        assert "!" not in filename
        assert "?" not in filename
        assert filename.endswith(".pdf")

    def test_get_pdf_filename_long_title(self):
        """Test filename truncation for long titles."""
        long_title = "A" * 200
        filename = get_pdf_filename(long_title, profile_type="report")
        assert len(filename) < 150  # Should be truncated
        assert filename.endswith(".pdf")
        assert "report" in filename


class TestPDFGeneration:
    """Tests for PDF generation (requires weasyprint)."""

    def test_markdown_to_pdf_basic(self):
        """Test basic markdown to PDF conversion."""
        markdown = """# Test Report

## Overview
This is a test report with **bold** and *italic* text.

## Findings
- Point 1
- Point 2
- Point 3

## Conclusion
Test complete.
"""
        pdf_bytes = markdown_to_pdf(
            markdown_content=markdown,
            title="Test Report",
            style="minimal",
        )

        assert pdf_bytes is not None
        assert len(pdf_bytes.getvalue()) > 1000  # PDF should be substantial
        assert pdf_bytes.getvalue().startswith(b"%PDF")  # Valid PDF header

    def test_markdown_to_pdf_with_metadata(self):
        """Test PDF generation with metadata."""
        markdown = "# Report\n\nContent here."
        metadata = {
            "Query": "test query",
            "Profile Type": "Company",
            "Generated": "2024-01-01 12:00:00",
        }

        pdf_bytes = markdown_to_pdf(
            markdown_content=markdown,
            title="Test Report",
            metadata=metadata,
            style="professional",
        )

        assert pdf_bytes is not None
        assert len(pdf_bytes.getvalue()) > 1000

    def test_markdown_to_pdf_professional_style(self):
        """Test PDF with professional styling."""
        markdown = """# Executive Summary

## Company Overview
Tesla is a leading electric vehicle manufacturer.

## Key Findings
1. Innovation leader
2. Strong brand
3. Global expansion

## Citations
[1] Source 1
[2] Source 2
"""
        pdf_bytes = markdown_to_pdf(
            markdown_content=markdown,
            title="Tesla Profile",
            metadata={"Type": "Company Profile"},
            style="professional",
        )

        assert pdf_bytes is not None
        assert pdf_bytes.getvalue().startswith(b"%PDF")

    def test_markdown_to_pdf_detailed_style(self):
        """Test PDF with detailed styling."""
        markdown = (
            "# Detailed Report\n\n## Section 1\nContent\n\n## Section 2\nMore content"
        )

        pdf_bytes = markdown_to_pdf(
            markdown_content=markdown,
            title="Detailed Report",
            style="detailed",
        )

        assert pdf_bytes is not None
        assert len(pdf_bytes.getvalue()) > 1000

    def test_markdown_to_pdf_with_code_blocks(self):
        """Test PDF generation with code blocks."""
        markdown = """# Technical Report

## Code Example
```python
def hello():
    print("Hello, world!")
```

## Output
The code prints: `Hello, world!`
"""
        pdf_bytes = markdown_to_pdf(
            markdown_content=markdown,
            title="Technical Report",
            style="professional",
        )

        assert pdf_bytes is not None
        assert pdf_bytes.getvalue().startswith(b"%PDF")

    def test_markdown_to_pdf_with_tables(self):
        """Test PDF generation with markdown tables."""
        markdown = """# Data Report

## Results Table

| Metric | Value | Status |
|--------|-------|--------|
| Revenue | $100M | ✓ |
| Growth | 25% | ✓ |
| Profit | $20M | ✓ |

## Analysis
Table shows strong performance.
"""
        pdf_bytes = markdown_to_pdf(
            markdown_content=markdown,
            title="Data Report",
            style="professional",
        )

        assert pdf_bytes is not None
        assert len(pdf_bytes.getvalue()) > 1000

    def test_markdown_to_pdf_empty_content(self):
        """Test PDF generation with empty content."""
        pdf_bytes = markdown_to_pdf(
            markdown_content="",
            title="Empty Report",
            style="minimal",
        )

        # Should still generate a PDF (with title/header)
        assert pdf_bytes is not None
        assert pdf_bytes.getvalue().startswith(b"%PDF")

    def test_markdown_to_pdf_unicode_content(self):
        """Test PDF generation with unicode characters."""
        markdown = """# International Report

## Overview
测试 (Chinese) • тест (Russian) • テスト (Japanese)

## Emojis
✅ Success • 🚀 Launch • 📊 Data • ❌ Error

## Symbols
→ ← ↑ ↓ • ★ ☆ • © ® ™
"""
        pdf_bytes = markdown_to_pdf(
            markdown_content=markdown,
            title="Unicode Test",
            style="professional",
        )

        assert pdf_bytes is not None
        assert pdf_bytes.getvalue().startswith(b"%PDF")
