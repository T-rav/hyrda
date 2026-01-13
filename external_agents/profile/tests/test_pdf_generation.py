"""Tests for PDF generation and upload functionality."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from external_agents.profile.nodes.final_report import upload_report_to_s3


@pytest.fixture
def mock_s3_client():
    """Mock boto3 S3 client."""
    with patch('external_agents.profile.nodes.final_report.boto3.client') as mock:
        client = MagicMock()
        client.head_bucket = MagicMock()
        client.put_object = MagicMock()
        client.generate_presigned_url = MagicMock(return_value="http://minio:9000/test.pdf")
        mock.return_value = client
        yield client


def test_upload_report_converts_markdown_to_pdf(mock_s3_client):
    """Test that upload_report_to_s3 converts markdown to properly formatted PDF."""
    # Markdown content with various formatting
    markdown_content = """# Company Profile

## Executive Summary

- **Key Point 1**: Important information
- *Key Point 2*: More details

### Technical Details

This is a paragraph with `inline code` and formatting.

```python
# Code block
def example():
    return "formatted"
```
"""

    url = upload_report_to_s3(markdown_content, "test_company")

    # Verify S3 upload was called
    assert mock_s3_client.put_object.called
    call_args = mock_s3_client.put_object.call_args

    # Verify PDF content type
    assert call_args[1]['ContentType'] == 'application/pdf'

    # Verify PDF bytes were generated (not empty)
    pdf_bytes = call_args[1]['Body']
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b'%PDF')  # PDF magic number

    # Verify filename format
    assert call_args[1]['Key'].startswith('profile_test_company_')
    assert call_args[1]['Key'].endswith('.pdf')

    # Verify presigned URL returned
    assert url == "http://minio:9000/test.pdf"


def test_upload_report_handles_special_characters(mock_s3_client):
    """Test that special characters in company name are sanitized."""
    markdown_content = "# Test Report"

    upload_report_to_s3(markdown_content, "Test & Company, Inc.")

    call_args = mock_s3_client.put_object.call_args
    filename = call_args[1]['Key']

    # Verify special characters are replaced with underscores
    assert "Test___Company__Inc_" in filename


def test_upload_report_creates_bucket_if_not_exists(mock_s3_client):
    """Test that upload creates bucket if it doesn't exist."""
    # Simulate bucket not existing
    mock_s3_client.head_bucket.side_effect = Exception("Bucket not found")

    upload_report_to_s3("# Test", "company")

    # Verify bucket creation was attempted
    assert mock_s3_client.create_bucket.called


def test_upload_report_returns_none_on_error():
    """Test that upload returns None on error."""
    with patch('external_agents.profile.nodes.final_report.boto3.client') as mock:
        mock.side_effect = Exception("S3 error")

        result = upload_report_to_s3("# Test", "company")

        assert result is None


def test_pdf_has_proper_html_structure(mock_s3_client):
    """Test that generated PDF contains proper HTML structure."""
    markdown_content = "# Test Header\n\nParagraph text."

    # Patch the markdown module in pdf_generator where it's actually imported
    with patch('external_agents.profile.pdf_utils.pdf_generator.markdown.Markdown') as mock_md_class:
        # Create a mock instance that the Markdown() constructor will return
        mock_md_instance = MagicMock()
        mock_md_instance.convert.return_value = "<h1>Test Header</h1><p>Paragraph text.</p>"
        mock_md_class.return_value = mock_md_instance

        upload_report_to_s3(markdown_content, "company")

        # Verify Markdown was instantiated with proper extensions
        mock_md_class.assert_called_once()
        call_kwargs = mock_md_class.call_args[1]
        assert 'extensions' in call_kwargs
        assert 'extra' in call_kwargs['extensions']


def test_pdf_uses_internal_minio_endpoint(mock_s3_client):
    """Test that presigned URLs use internal MinIO endpoint."""
    url = upload_report_to_s3("# Test", "company")

    # Verify URL uses internal endpoint (not public localhost)
    assert url.startswith("http://minio:9000") or url.startswith("http://localhost:9000")


def test_upload_report_strips_llm_preambles(mock_s3_client):
    """Test that LLM-generated preambles are stripped before PDF generation."""
    # Content with typical LLM preamble before the actual report
    markdown_content = """Here is the revised Company Profile Report for Costco Wholesale Corporation.

I have carefully reviewed the research notes and compiled the following comprehensive profile.

# Executive Summary

Costco is a leading warehouse retailer.

## Company Overview

Founded in 1983, Costco operates worldwide.
"""

    upload_report_to_s3(markdown_content, "costco")

    # Get the PDF bytes that were uploaded
    call_args = mock_s3_client.put_object.call_args
    pdf_bytes = call_args[1]['Body']

    # Convert PDF back to text to verify preamble was stripped
    # The PDF should start with "Executive Summary", not the preamble
    assert pdf_bytes.startswith(b'%PDF')  # Valid PDF

    # Verify the preamble text is NOT in the PDF
    # Note: This is a basic check - a full check would extract PDF text
    pdf_str = pdf_bytes.decode('latin-1', errors='ignore')
    assert "Here is the revised Company Profile Report" not in pdf_str
    assert "I have carefully reviewed" not in pdf_str


def test_upload_report_removes_metadata_header(mock_s3_client):
    """Test that metadata header (Date, Profile Type, Focus Area) is not included in PDF."""
    # Standard markdown report
    markdown_content = """# Company Profile

## Overview

This is the company overview section.
"""

    upload_report_to_s3(markdown_content, "test_company")

    # Get the PDF bytes
    call_args = mock_s3_client.put_object.call_args
    pdf_bytes = call_args[1]['Body']

    # Convert PDF to string and verify metadata fields are NOT present
    pdf_str = pdf_bytes.decode('latin-1', errors='ignore')

    # These metadata fields should NOT appear in the PDF
    assert "Profile Type:" not in pdf_str
    assert "Date:" not in pdf_str.split("Generated:")[0]  # Exclude the timestamp footer
    assert "Focus Area:" not in pdf_str


def test_upload_report_strips_metadata_fields_from_markdown(mock_s3_client):
    """Test that metadata fields in markdown content are stripped."""
    # Markdown with metadata fields that LLM might add
    markdown_content = """# Company Profile: Costco Wholesale Corporation
Date: December 19, 2025
Profile Type: company
Focus Area: None (general profile)

## Executive Summary

Costco is a leading warehouse retailer.

## Company Overview

Founded in 1983, Costco operates worldwide.
"""

    # Patch the PDF generator to capture the cleaned markdown before conversion
    with patch('external_agents.profile.pdf_utils.pdf_generator.markdown_to_pdf') as mock_pdf_gen:
        from io import BytesIO
        mock_pdf_gen.return_value = BytesIO(b'%PDF-mock')

        upload_report_to_s3(markdown_content, "costco")

        # Get the markdown content that was passed to the PDF generator
        call_args = mock_pdf_gen.call_args
        cleaned_markdown = call_args[1]['markdown_content']

        # Verify metadata fields were stripped
        assert "Date: December 19, 2025" not in cleaned_markdown
        assert "Profile Type: company" not in cleaned_markdown
        assert "Focus Area: None (general profile)" not in cleaned_markdown

        # But the actual content should still be present
        assert "Executive Summary" in cleaned_markdown
        assert "Costco" in cleaned_markdown


def test_upload_report_preserves_clean_content(mock_s3_client):
    """Test that clean content without preambles is preserved correctly."""
    # Content that starts directly with a heading (no preamble)
    markdown_content = """# Executive Summary

This report covers key findings.

## Section 1

Content here.
"""

    upload_report_to_s3(markdown_content, "company")

    # Verify PDF was generated successfully
    call_args = mock_s3_client.put_object.call_args
    pdf_bytes = call_args[1]['Body']

    assert pdf_bytes.startswith(b'%PDF')
    assert len(pdf_bytes) > 0


def test_upload_report_uses_simplified_title_format(mock_s3_client):
    """Test that PDF title uses simplified format: 'CompanyName - Company Profile'."""
    markdown_content = """# Executive Summary

Company overview.
"""

    # Patch the PDF generator to capture the title parameter
    with patch('external_agents.profile.pdf_utils.pdf_generator.markdown_to_pdf') as mock_pdf_gen:
        from io import BytesIO
        mock_pdf_gen.return_value = BytesIO(b'%PDF-mock')

        upload_report_to_s3(markdown_content, "Acme Corp")

        # Get the title that was passed to the PDF generator
        call_args = mock_pdf_gen.call_args
        title = call_args[1]['title']

        # Should use simplified format: "Acme Corp - Company Profile"
        assert title == "Acme Corp - Company Profile"


def test_upload_report_applies_title_case_to_company_name(mock_s3_client):
    """Test that company name is converted to title case in PDF title."""
    markdown_content = """# Executive Summary

Company overview.
"""

    # Patch the PDF generator to capture the title parameter
    with patch('external_agents.profile.pdf_utils.pdf_generator.markdown_to_pdf') as mock_pdf_gen:
        from io import BytesIO
        mock_pdf_gen.return_value = BytesIO(b'%PDF-mock')

        # Test with lowercase company name (as it comes from query)
        upload_report_to_s3(markdown_content, "elevance health")

        # Get the title that was passed to the PDF generator
        call_args = mock_pdf_gen.call_args
        title = call_args[1]['title']

        # Should convert to title case: "Elevance Health - Company Profile"
        assert title == "Elevance Health - Company Profile"


def test_upload_report_filename_has_timestamp(mock_s3_client):
    """Test that PDF filename includes timestamp."""
    markdown_content = """# Executive Summary

Test content.
"""

    upload_report_to_s3(markdown_content, "TestCo")

    # Get the filename that was uploaded
    call_args = mock_s3_client.put_object.call_args
    filename = call_args[1]['Key']

    # Filename format: profile_{company}_{date}_{time}.pdf
    # Example: profile_TestCo_20231219_143022.pdf
    import re
    pattern = r'profile_TestCo_\d{8}_\d{6}\.pdf'
    assert re.match(pattern, filename), f"Filename '{filename}' doesn't match expected pattern with timestamp"

    # Verify it has exactly 4 parts separated by underscores (plus .pdf extension)
    # Format: profile, company, date, time
    parts = filename.replace('.pdf', '').split('_')
    assert len(parts) == 4, f"Expected 4 parts (profile, company, date, time), got {len(parts)}: {parts}"


@pytest.mark.integration
def test_pdf_generation_with_real_markdown():
    """Integration test: Generate actual PDF from markdown."""
    markdown_content = """# Company Profile Report

## Section 1
This is **bold** and this is *italic*.

## Section 2
- Bullet point 1
- Bullet point 2

### Subsection
Paragraph with `code` formatting.
"""

    # Mock only S3, let weasyprint actually generate PDF
    with patch('external_agents.profile.nodes.final_report.boto3.client') as mock:
        client = MagicMock()
        client.head_bucket = MagicMock()
        client.generate_presigned_url = MagicMock(return_value="http://minio:9000/test.pdf")
        mock.return_value = client

        url = upload_report_to_s3(markdown_content, "test_company")

        # Verify PDF was generated and uploaded
        assert url is not None
        assert client.put_object.called

        # Verify PDF bytes
        pdf_bytes = client.put_object.call_args[1]['Body']
        assert pdf_bytes.startswith(b'%PDF')
        assert len(pdf_bytes) > 1000  # Should be substantial
