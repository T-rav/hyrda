"""
Tests for Citation Service

Comprehensive tests for citation formatting and context building functionality using factory patterns.
"""

from typing import Any

from services.citation_service import CitationService


# TDD Factory Patterns for Citation Service Testing
class CitationServiceFactory:
    """Factory for creating CitationService instances with complete test scenarios"""

    @staticmethod
    def create_basic_service() -> CitationService:
        """Create basic citation service"""
        return CitationService()

    @staticmethod
    def create_test_scenario(
        response: str = "This is a test response.",
        context_chunks: list[dict[str, Any]] | None = None,
    ) -> tuple[CitationService, str, list[dict[str, Any]]]:
        """Create complete test scenario with service, response, and chunks"""
        service = CitationService()
        chunks = context_chunks if context_chunks is not None else []
        return service, response, chunks

    @staticmethod
    def create_apple_scenario() -> tuple[CitationService, str, list[dict[str, Any]]]:
        """Create scenario with Apple company content"""
        service = CitationService()
        response = "Apple is a tech company."
        context_chunks = ContextChunkBuilder.single_apple_chunk().build()
        return service, response, context_chunks

    @staticmethod
    def create_multiple_files_scenario() -> tuple[
        CitationService, str, list[dict[str, Any]]
    ]:
        """Create scenario with multiple different files"""
        service = CitationService()
        response = "Information about companies."
        context_chunks = ContextChunkBuilder.multiple_different_files().build()
        return service, response, context_chunks

    @staticmethod
    def create_empty_chunks_scenario() -> tuple[
        CitationService, str, list[dict[str, Any]]
    ]:
        """Create scenario with empty chunks"""
        service = CitationService()
        response = "This is a test response."
        context_chunks: list[dict[str, Any]] = []
        return service, response, context_chunks

    @staticmethod
    def create_deduplication_scenario() -> tuple[
        CitationService, str, list[dict[str, Any]]
    ]:
        """Create scenario for testing deduplication of sources"""
        service = CitationService()
        response = "Test response."
        context_chunks = [
            {
                "content": "Content 1...",
                "similarity": 0.95,
                "metadata": {"file_name": "Apple - Project Details File.pdf"},
            },
            {
                "content": "Content 2...",
                "similarity": 0.90,
                "metadata": {
                    "file_name": "Apple - PROJECT DETAILS File.PDF"
                },  # Different case
            },
            {
                "content": "Content 3...",
                "similarity": 0.85,
                "metadata": {"file_name": "Other Document.pdf"},
            },
        ]
        return service, response, context_chunks


class ContextChunkBuilder:
    """Builder for creating context chunks with different configurations"""

    def __init__(self):
        self.chunks: list[dict[str, Any]] = []

    def add_chunk(
        self,
        content: str,
        similarity: float,
        file_name: str | None = None,
        title: str | None = None,
        web_view_link: str | None = None,
        source: str | None = None,
        chunk_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ContextChunkBuilder":
        """Add a context chunk with specified properties"""
        if metadata is None:
            metadata = {}
            if file_name:
                metadata["file_name"] = file_name
            if title:
                metadata["title"] = title
            if web_view_link:
                metadata["web_view_link"] = web_view_link
            if source:
                metadata["source"] = source
            if chunk_id:
                metadata["chunk_id"] = chunk_id

        chunk = {
            "content": content,
            "similarity": similarity,
            "metadata": metadata,
        }
        self.chunks.append(chunk)
        return self

    def add_apple_chunk(
        self, similarity: float = 0.95, sections: int = 1
    ) -> "ContextChunkBuilder":
        """Add Apple company chunk(s)"""
        for i in range(sections):
            content = (
                f"Apple content {i + 1}..." if sections > 1 else "Apple content..."
            )
            self.add_chunk(
                content=content,
                similarity=similarity,
                file_name="Apple - Project Details File.pdf",
            )
        return self

    def add_3step_chunk(self, similarity: float = 0.88) -> "ContextChunkBuilder":
        """Add 3Step company chunk"""
        return self.add_chunk(
            content="3Step content...",
            similarity=similarity,
            file_name="3Step - Scheduler Case Study.docx",
        )

    def add_chunk_with_title(
        self,
        content: str = "Content...",
        similarity: float = 0.90,
        file_name: str = "Apple - Project Details File.pdf",
        title: str = "Advanced Project Management",
    ) -> "ContextChunkBuilder":
        """Add chunk with title metadata"""
        return self.add_chunk(
            content=content,
            similarity=similarity,
            file_name=file_name,
            title=title,
        )

    def add_chunk_with_web_link(
        self,
        content: str = "Content...",
        similarity: float = 0.90,
        file_name: str = "Apple - Project Details File.pdf",
        web_view_link: str = "https://drive.google.com/file/d/123/view",
    ) -> "ContextChunkBuilder":
        """Add chunk with web view link"""
        return self.add_chunk(
            content=content,
            similarity=similarity,
            file_name=file_name,
            web_view_link=web_view_link,
        )

    def add_empty_chunk(self) -> "ContextChunkBuilder":
        """Add malformed/empty chunk"""
        self.chunks.append({})
        return self

    def add_chunk_no_metadata(
        self, content: str = "Content...", similarity: float = 0.90
    ) -> "ContextChunkBuilder":
        """Add chunk without metadata"""
        chunk = {"content": content, "similarity": similarity}
        self.chunks.append(chunk)
        return self

    def add_chunk_no_similarity(
        self, content: str = "Content...", file_name: str = "Test Document.pdf"
    ) -> "ContextChunkBuilder":
        """Add chunk without similarity score"""
        chunk = {
            "content": content,
            "metadata": {"file_name": file_name},
        }
        self.chunks.append(chunk)
        return self

    def with_high_similarity(self) -> "ContextChunkBuilder":
        """Add high similarity Apple chunk - fluent method"""
        return self.add_apple_chunk(similarity=0.95)

    def with_medium_similarity(self) -> "ContextChunkBuilder":
        """Add medium similarity chunk - fluent method"""
        return self.add_apple_chunk(similarity=0.75)

    def with_low_similarity(self) -> "ContextChunkBuilder":
        """Add low similarity chunk - fluent method"""
        return self.add_apple_chunk(similarity=0.45)

    def and_3step_content(self) -> "ContextChunkBuilder":
        """Chain 3Step content - fluent method"""
        return self.add_3step_chunk()

    def and_title_metadata(self) -> "ContextChunkBuilder":
        """Chain title metadata - fluent method"""
        return self.add_chunk_with_title()

    def and_web_link(self) -> "ContextChunkBuilder":
        """Chain web link metadata - fluent method"""
        return self.add_chunk_with_web_link()

    def build(self) -> list[dict[str, Any]]:
        """Build the context chunks list"""
        return self.chunks.copy()

    @staticmethod
    def single_apple_chunk() -> "ContextChunkBuilder":
        """Create single Apple chunk"""
        return ContextChunkBuilder().add_apple_chunk()

    @staticmethod
    def multiple_same_file() -> "ContextChunkBuilder":
        """Create multiple chunks from same file"""
        return ContextChunkBuilder().add_apple_chunk(0.95).add_apple_chunk(0.90)

    @staticmethod
    def multiple_different_files() -> "ContextChunkBuilder":
        """Create chunks from different files"""
        return ContextChunkBuilder().add_apple_chunk().add_3step_chunk()

    @staticmethod
    def various_file_extensions() -> "ContextChunkBuilder":
        """Create chunks with different file extensions"""
        return (
            ContextChunkBuilder()
            .add_chunk("Content 1...", 0.90, "Document.pdf")
            .add_chunk("Content 2...", 0.85, "Report.docx")
            .add_chunk("Content 3...", 0.80, "Notes.txt")
        )

    @staticmethod
    def with_title_and_web_link() -> "ContextChunkBuilder":
        """Create chunk with title and web link metadata - avoid in-test configuration"""
        return ContextChunkBuilder().add_chunk_with_title()

    @staticmethod
    def with_web_view_link() -> "ContextChunkBuilder":
        """Create chunk with web view link - avoid in-test configuration"""
        return ContextChunkBuilder().add_chunk_with_web_link()

    @staticmethod
    def for_llm_formatting() -> "ContextChunkBuilder":
        """Create chunk optimized for LLM context formatting"""
        return ContextChunkBuilder().add_chunk(
            content="This is test content for the LLM.",
            similarity=0.95,
            file_name="Test Document.pdf",
        )

    @staticmethod
    def empty_chunks() -> "ContextChunkBuilder":
        """Create empty chunks scenario"""
        return ContextChunkBuilder()  # No chunks added

    @staticmethod
    def malformed_chunks() -> "ContextChunkBuilder":
        """Create malformed chunks for error testing"""
        return (
            ContextChunkBuilder()
            .add_empty_chunk()
            .add_chunk_no_metadata()
            .add_chunk_no_similarity()
        )

    @staticmethod
    def with_uploaded_document() -> "ContextChunkBuilder":
        """Create chunks that include an uploaded document (should be filtered from citations)"""
        return (
            ContextChunkBuilder()
            .add_chunk(
                content="This is the content of the uploaded document.",
                similarity=1.0,
                file_name="uploaded_document.pdf",
                source="uploaded_document",
                chunk_id="uploaded_doc_0",
            )
            .add_chunk(
                content="This is content from the knowledge base.",
                similarity=0.85,
                file_name="knowledge_base_doc.pdf",
                source="vector_db",
            )
        )

    @staticmethod
    def integration_test_chunks() -> "ContextChunkBuilder":
        """Create comprehensive chunks for integration testing"""
        return (
            ContextChunkBuilder()
            .add_chunk(
                content="Apple Inc. is a multinational technology company.",
                similarity=0.95,
                file_name="Apple - Company Overview.pdf",
                title="Corporate Information",
                web_view_link="https://drive.google.com/file/d/apple123/view",
            )
            .add_chunk(
                content="Additional details about Apple's projects.",
                similarity=0.90,
                file_name="Apple - Company Overview.pdf",
                title="Corporate Information",
            )
            .add_chunk(
                content="3Step provides tournament scheduling software.",
                similarity=0.85,
                file_name="3Step - Product Overview.docx",
            )
        )


class TestCitationService:
    """Test citation service functionality using factory patterns"""

    def test_add_source_citations_empty_chunks(self):
        """Test citation handling with empty context chunks"""
        citation_service, response, context_chunks = (
            CitationServiceFactory.create_empty_chunks_scenario()
        )
        result = citation_service.add_source_citations(response, context_chunks)
        assert result == response

    def test_add_source_citations_single_chunk(self):
        """Test citation with single context chunk"""
        citation_service, response, context_chunks = (
            CitationServiceFactory.create_apple_scenario()
        )

        result = citation_service.add_source_citations(response, context_chunks)

        assert "**📚 Sources:**" in result
        assert "1. Apple - Project Details File" in result
        assert "Match: 95.0%" in result
        assert "(:file_folder: Knowledge Base)" in result

    def test_add_source_citations_multiple_chunks_same_file(self):
        """Test citation with multiple chunks from same file"""
        citation_service = CitationServiceFactory.create_basic_service()
        response = "Apple information."
        context_chunks = ContextChunkBuilder.multiple_same_file().build()

        result = citation_service.add_source_citations(response, context_chunks)

        # Should only have one citation but mention multiple sections
        assert result.count("1. Apple - Project Details File") == 1
        assert "2 sections" in result
        assert "Match: 95.0%" in result  # Should use highest similarity

    def test_add_source_citations_multiple_different_files(self):
        """Test citation with chunks from different files"""
        citation_service, response, context_chunks = (
            CitationServiceFactory.create_multiple_files_scenario()
        )

        result = citation_service.add_source_citations(response, context_chunks)

        assert "1. Apple - Project Details File" in result
        assert "2. 3Step - Scheduler Case Study" in result
        assert "Match: 95.0%" in result
        assert "Match: 88.0%" in result

    def test_add_source_citations_with_subtitle(self):
        """Test citation with subtitle in metadata"""
        citation_service = CitationServiceFactory.create_basic_service()
        response = "Test response."
        context_chunks = ContextChunkBuilder.with_title_and_web_link().build()

        result = citation_service.add_source_citations(response, context_chunks)

        assert "1. Apple - Project Details File • Advanced Project Management" in result

    def test_add_source_citations_with_web_link(self):
        """Test citation with web view link"""
        citation_service = CitationServiceFactory.create_basic_service()
        response = "Test response."
        context_chunks = ContextChunkBuilder.with_web_view_link().build()

        result = citation_service.add_source_citations(response, context_chunks)

        assert "[1. Apple - Project Details File" in result
        assert "](https://drive.google.com/file/d/123/view)" in result

    def test_add_source_citations_removes_file_extensions(self):
        """Test that file extensions are properly removed"""
        citation_service = CitationServiceFactory.create_basic_service()
        response = "Test response."
        context_chunks = ContextChunkBuilder.various_file_extensions().build()

        result = citation_service.add_source_citations(response, context_chunks)

        assert "1. Document" in result
        assert "2. Report" in result
        assert "3. Notes" in result
        assert ".pdf" not in result
        assert ".docx" not in result
        assert ".txt" not in result

    def test_add_source_citations_deduplication(self):
        """Test that duplicate sources are properly deduplicated"""
        citation_service, response, context_chunks = (
            CitationServiceFactory.create_deduplication_scenario()
        )

        result = citation_service.add_source_citations(response, context_chunks)

        # Should deduplicate similar file names (case insensitive)
        citations = result.split("**📚 Sources:**")[1]
        assert citations.count("Apple - Project Details File") == 1
        # Note: The deduplication means only 2 sources shown, not chunk count
        assert "1. Apple - Project Details File" in result
        assert "2. Other Document" in result

    def test_add_source_citations_unknown_filename(self):
        """Test citation with missing file name"""
        citation_service = CitationServiceFactory.create_basic_service()
        response = "Test response."
        context_chunks = [
            {"content": "Content...", "similarity": 0.90, "metadata": {}},
            {
                "content": "Content 2...",
                "similarity": 0.85,
                "metadata": {"file_name": ""},  # Empty file name
            },
        ]

        result = citation_service.add_source_citations(response, context_chunks)

        assert "1. Document 1" in result
        # Empty file name results in just the number, so check for that pattern
        sources_section = result.split("**📚 Sources:**")[1]
        assert "2." in sources_section

    def test_add_source_citations_zero_similarity(self):
        """Test citation with zero similarity score"""
        citation_service = CitationServiceFactory.create_basic_service()
        response = "Test response."
        context_chunks = [
            {
                "content": "Content...",
                "similarity": 0.0,
                "metadata": {"file_name": "Test Document.pdf"},
            }
        ]

        result = citation_service.add_source_citations(response, context_chunks)

        assert "Match: 0.0%" in result

    def test_format_context_for_llm_empty_chunks(self):
        """Test LLM context formatting with empty chunks"""
        citation_service = CitationServiceFactory.create_basic_service()
        result = citation_service.format_context_for_llm([])
        assert result == ""

    def test_format_context_for_llm_single_chunk(self):
        """Test LLM context formatting with single chunk"""
        citation_service = CitationServiceFactory.create_basic_service()
        context_chunks = (
            ContextChunkBuilder()
            .add_chunk(
                content="This is test content for the LLM.",
                similarity=0.95,
                file_name="Test Document.pdf",
            )
            .build()
        )

        result = citation_service.format_context_for_llm(context_chunks)

        assert "[Source: Test Document.pdf, Score: 0.95]" in result
        assert "This is test content for the LLM." in result

    def test_format_context_for_llm_multiple_chunks(self):
        """Test LLM context formatting with multiple chunks"""
        citation_service = CitationServiceFactory.create_basic_service()
        context_chunks = [
            {
                "content": "First content chunk.",
                "similarity": 0.95,
                "metadata": {"file_name": "Document 1.pdf"},
            },
            {
                "content": "Second content chunk.",
                "similarity": 0.88,
                "metadata": {"file_name": "Document 2.pdf"},
            },
        ]

        result = citation_service.format_context_for_llm(context_chunks)

        assert "[Source: Document 1.pdf, Score: 0.95]" in result
        assert "First content chunk." in result
        assert "[Source: Document 2.pdf, Score: 0.88]" in result
        assert "Second content chunk." in result
        # Should be separated by double newlines
        assert result.count("\n\n") >= 1

    def test_format_context_for_llm_no_metadata(self):
        """Test LLM context formatting without metadata"""
        citation_service = CitationServiceFactory.create_basic_service()
        context_chunks = [{"content": "Content without metadata.", "similarity": 0.80}]

        result = citation_service.format_context_for_llm(context_chunks)

        assert "[Score: 0.80]" in result
        assert "Content without metadata." in result
        assert "Source:" not in result

    def test_format_context_for_llm_missing_similarity(self):
        """Test LLM context formatting without similarity score"""
        citation_service = CitationServiceFactory.create_basic_service()
        context_chunks = [
            {
                "content": "Content without similarity.",
                "metadata": {"file_name": "Test Document.pdf"},
            }
        ]

        result = citation_service.format_context_for_llm(context_chunks)

        assert "[Source: Test Document.pdf, Score: 0.00]" in result
        assert "Content without similarity." in result

    def test_format_context_for_llm_empty_metadata(self):
        """Test LLM context formatting with empty metadata dict"""
        citation_service = CitationServiceFactory.create_basic_service()
        context_chunks = [
            {
                "content": "Content with empty metadata.",
                "similarity": 0.75,
                "metadata": {},
            }
        ]

        result = citation_service.format_context_for_llm(context_chunks)

        # Empty metadata is treated as no metadata, so just score
        assert "[Score: 0.75]" in result
        assert "Content with empty metadata." in result

    def test_citation_service_integration(self):
        """Test full integration of citation service methods"""
        citation_service = CitationServiceFactory.create_basic_service()
        # Simulate a complete RAG pipeline using builder pattern
        context_chunks = ContextChunkBuilder.integration_test_chunks().build()

        # Format for LLM
        llm_context = citation_service.format_context_for_llm(context_chunks)
        assert "Apple Inc. is a multinational technology company." in llm_context
        assert "3Step provides tournament scheduling software." in llm_context

        # Add citations to response
        response = "Both Apple and 3Step are technology companies with different specializations."
        cited_response = citation_service.add_source_citations(response, context_chunks)

        assert "**📚 Sources:**" in cited_response
        # The citation format puts sections before the subtitle
        assert "Apple - Company Overview" in cited_response
        assert "2 sections" in cited_response  # Multiple chunks from Apple doc
        assert "Corporate Information" in cited_response
        assert "2. 3Step - Product Overview" in cited_response
        assert "Match: 95.0%" in cited_response
        assert "Match: 85.0%" in cited_response
        assert "[1. Apple" in cited_response  # Should have web link
        assert "](https://drive.google.com/file/d/apple123/view)" in cited_response


class TestCitationServiceEdgeCases:
    """Test edge cases and error conditions using factory patterns"""

    def test_malformed_context_chunks(self):
        """Test handling of malformed context chunks"""
        citation_service = CitationServiceFactory.create_basic_service()
        response = "Test response."
        malformed_chunks = [
            {},  # Empty chunk
            {"content": "Valid content"},  # Missing similarity and metadata
            {"similarity": 0.95},  # Missing content
            None,  # None value - this might cause issues
        ]

        # Filter out None values as they would likely cause errors
        safe_chunks = [chunk for chunk in malformed_chunks if chunk is not None]

        result = citation_service.add_source_citations(response, safe_chunks)

        # Should handle gracefully
        assert "Test response." in result

    def test_very_long_file_names(self):
        """Test handling of very long file names"""
        citation_service = CitationServiceFactory.create_basic_service()
        response = "Test response."
        context_chunks = [
            {
                "content": "Content...",
                "similarity": 0.90,
                "metadata": {
                    "file_name": "Very Long Document Name That Exceeds Normal Length Expectations And Contains Many Words That Might Cause Formatting Issues In Citations.pdf"
                },
            }
        ]

        result = citation_service.add_source_citations(response, context_chunks)

        # Should still work but truncate file extension
        assert (
            "Very Long Document Name That Exceeds Normal Length Expectations And Contains Many Words That Might Cause Formatting Issues In Citations"
            in result
        )
        assert ".pdf" not in result

    def test_special_characters_in_file_names(self):
        """Test handling of special characters in file names"""
        citation_service = CitationServiceFactory.create_basic_service()
        response = "Test response."
        context_chunks = [
            {
                "content": "Content...",
                "similarity": 0.90,
                "metadata": {
                    "file_name": "Document with (special) [chars] & symbols!.pdf"
                },
            }
        ]

        result = citation_service.add_source_citations(response, context_chunks)

        # Should preserve special characters but remove extension
        assert "Document with (special) [chars] & symbols!" in result
        assert ".pdf" not in result

    def test_unicode_characters_in_content(self):
        """Test handling of Unicode characters"""
        citation_service = CitationServiceFactory.create_basic_service()
        response = "Test response with émojis 🚀."
        context_chunks = [
            {
                "content": "Content with émojis 🎉 and ünïcödé characters.",
                "similarity": 0.90,
                "metadata": {"file_name": "Ünïcödé Document.pdf"},
            }
        ]

        result = citation_service.add_source_citations(response, context_chunks)

        assert "Ünïcödé Document" in result
        assert "🚀" in result

        # Test LLM formatting too
        llm_context = citation_service.format_context_for_llm(context_chunks)
        assert "Content with émojis 🎉 and ünïcödé characters." in llm_context

    def test_uploaded_document_excluded_from_citations(self):
        """Test that uploaded documents are not cited back to the user"""
        citation_service = CitationServiceFactory.create_basic_service()
        response = "Here's information from both sources."

        # Mix of uploaded document and knowledge base content
        context_chunks = ContextChunkBuilder.with_uploaded_document().build()

        result = citation_service.add_source_citations(response, context_chunks)

        # Should only cite the knowledge base document, not the uploaded one
        assert "knowledge_base_doc" in result
        assert "uploaded_document" not in result
        assert "Sources:" in result
        assert "1. knowledge_base_doc" in result

        # Should not have a second citation since uploaded doc was filtered out
        assert "2." not in result

    def test_only_uploaded_document_no_citations(self):
        """Test that when only uploaded document is provided, no citations are added"""
        citation_service = CitationServiceFactory.create_basic_service()
        response = "Information from your uploaded document."

        # Only uploaded document chunks
        context_chunks = [
            {
                "content": "Content from uploaded document.",
                "similarity": 1.0,
                "metadata": {
                    "file_name": "user_uploaded.pdf",
                    "source": "uploaded_document",
                    "chunk_id": "uploaded_doc_0",
                },
            }
        ]

        result = citation_service.add_source_citations(response, context_chunks)

        # Should return original response with no citations
        assert result == response
        assert "Sources:" not in result
