"""
Tests for Title Injection Service using factory patterns

Validates title injection logic for enhanced RAG embeddings
"""

from services.title_injection_service import (
    EnhancedChunkProcessor,
    TitleInjectionService,
)


# TDD Factory Patterns for Title Injection Service Testing
class TitleInjectionServiceFactory:
    """Factory for creating TitleInjectionService instances"""

    @staticmethod
    def create_service() -> TitleInjectionService:
        """Create standard title injection service"""
        return TitleInjectionService()

    @staticmethod
    def create_custom_service(
        title_start_token: str = "<TITLE>",
        title_end_token: str = "</TITLE>",
        separator: str = " | ",
    ) -> TitleInjectionService:
        """Create service with custom tokens"""
        return TitleInjectionService(
            title_start_token=title_start_token,
            title_end_token=title_end_token,
            separator=separator,
        )


class DocumentDataFactory:
    """Factory for creating document test data"""

    @staticmethod
    def create_simple_document() -> dict:
        """Create simple document with title"""
        return {
            "content": "This is some content about AI.",
            "metadata": {"title": "Introduction to AI"},
        }

    @staticmethod
    def create_document_without_title() -> dict:
        """Create document without title"""
        return {
            "content": "Content without title.",
            "metadata": {},
        }

    @staticmethod
    def create_document_with_empty_title() -> dict:
        """Create document with empty title"""
        return {
            "content": "Some content.",
            "metadata": {"title": ""},
        }

    @staticmethod
    def create_multiple_documents() -> list[dict]:
        """Create multiple test documents"""
        return [
            {
                "content": "First document content.",
                "metadata": {"title": "Document One"},
            },
            {
                "content": "Second document content.",
                "metadata": {},  # No title
            },
            {
                "content": "Third document content.",
                "metadata": {"title": "Document Three"},
            },
        ]

    @staticmethod
    def create_documents_for_embedding() -> list[dict]:
        """Create documents for embedding processing"""
        return [
            {
                "content": "This is about machine learning.",
                "metadata": {"title": "ML Basics", "author": "John Doe"},
            },
            {
                "content": "Deep learning fundamentals.",
                "metadata": {"filename": "deep_learning.pdf"},
            },
        ]

    @staticmethod
    def create_document_for_dual_indexing() -> dict:
        """Create document for dual indexing test"""
        return {
            "content": "Content about AI safety.",
            "metadata": {"title": "AI Safety Guide", "category": "safety"},
        }

    @staticmethod
    def create_document_with_unicode() -> dict:
        """Create document with unicode title"""
        return {
            "content": "Content with unicode.",
            "metadata": {"title": "Título con acentos 中文 🚀"},
        }

    @staticmethod
    def create_document_with_long_title() -> dict:
        """Create document with very long title"""
        return {
            "content": "Short content.",
            "metadata": {"title": "A" * 1000},  # 1000 character title
        }


class MetadataTestDataFactory:
    """Factory for creating metadata test cases"""

    @staticmethod
    def create_title_extraction_test_cases() -> list[tuple]:
        """Create test cases for title extraction"""
        return [
            ({"title": "Main Title"}, "Main Title"),
            ({"document_title": "Doc Title"}, "Doc Title"),
            ({"file_name": "file.pdf"}, "File"),  # Filename processed
            ({"filename": "report.docx"}, "Report"),  # Filename processed
            ({"name": "Analysis"}, "Analysis"),  # Not a filename
            ({"doc_title": "Research"}, "Research"),
            ({"heading": "Chapter 1"}, "Chapter 1"),
            ({"header": "Section A"}, "Section A"),
            ({}, None),  # No title keys
            ({"title": ""}, None),  # Empty title
            ({"title": "   "}, None),  # Whitespace only
        ]

    @staticmethod
    def create_filename_test_cases() -> list[tuple]:
        """Create filename title extraction test cases"""
        return [
            # Basic PDF files
            (
                {"file_name": "Apple - Project Details File.pdf"},
                "Apple Project Details File",
            ),
            ({"file_name": "Machine Learning Guide.pdf"}, "Machine Learning Guide"),
            ({"file_name": "user_manual_v2.pdf"}, "User Manual V2"),
            # Different file types
            ({"file_name": "quarterly_report.docx"}, "Quarterly Report"),
            ({"file_name": "data_analysis.xlsx"}, "Data Analysis"),
            ({"file_name": "presentation_slides.pptx"}, "Presentation Slides"),
            ({"file_name": "meeting_notes.txt"}, "Meeting Notes"),
            # Company prefix patterns
            (
                {"file_name": "Microsoft - Azure Documentation.pdf"},
                "Microsoft Azure Documentation",
            ),
            (
                {"file_name": "Google - Cloud Security Guide.docx"},
                "Google Cloud Security Guide",
            ),
            ({"file_name": "Slack - API Reference.pdf"}, "Slack API Reference"),
            # Complex patterns
            ({"file_name": "2023_Annual_Report_Final.pdf"}, "2023 Annual Report Final"),
            ({"file_name": "AI_ML_Best_Practices.docx"}, "AI ML Best Practices"),
            # Non-filename text (should not be processed)
            (
                {"file_name": "Simple Title Without Extension"},
                "Simple Title Without Extension",
            ),
            ({"title": "Regular Title"}, "Regular Title"),
            # Edge cases
            ({"file_name": "a.pdf"}, "a.pdf"),  # Too short, keep original
            ({"file_name": ".hidden.pdf"}, ".hidden.pdf"),  # Hidden file, keep original
        ]

    @staticmethod
    def create_filename_detection_cases() -> list[tuple]:
        """Create filename detection test cases"""
        return [
            ("document.pdf", True),
            ("spreadsheet.xlsx", True),
            ("presentation.pptx", True),
            ("text_file.txt", True),
            ("webpage.html", True),
            ("config.json", True),
            ("Regular Title", False),
            ("Title With Spaces", False),
            ("123456", False),
            ("", False),
        ]

    @staticmethod
    def create_filename_conversion_cases() -> list[tuple]:
        """Create filename to title conversion test cases"""
        return [
            ("Apple - Project Details File.pdf", "Apple Project Details File"),
            ("Machine_Learning_Guide.pdf", "Machine Learning Guide"),
            ("quarterly-report-2023.docx", "Quarterly Report 2023"),
            ("API_REFERENCE_v2.1.pdf", "API Reference V2.1"),
            ("ml_basics.txt", "ML Basics"),
            ("user_interface_design.pptx", "User Interface Design"),
            ("simple.pdf", "Simple"),
            ("a.pdf", "a.pdf"),  # Too short, keep original
        ]

    @staticmethod
    def create_pattern_cleaning_cases() -> list[tuple]:
        """Create filename pattern cleaning test cases"""
        return [
            ("Apple - Project Details File", "Apple Project Details File"),
            ("Microsoft - Azure Documentation", "Microsoft Azure Documentation"),
            ("user_manual_v2", "User Manual V2"),
            ("API_REFERENCE_final", "API Reference Final"),
            ("machine_learning_guide", "Machine Learning Guide"),
            ("quarterly  report   2023", "Quarterly Report 2023"),
            ("ai_ml_basics", "AI ML Basics"),
            ("ios_development", "iOS Development"),
            ("json_api_guide", "JSON API Guide"),
        ]


class TextDataFactory:
    """Factory for creating text test data"""

    @staticmethod
    def create_enhanced_text() -> str:
        """Create enhanced text with title injection"""
        return "[FILENAME] Test Title [/FILENAME]\nSome content here."

    @staticmethod
    def create_plain_text() -> str:
        """Create plain text without title injection"""
        return "Just some regular content without title tags."

    @staticmethod
    def create_malformed_texts() -> list[str]:
        """Create malformed enhanced text cases"""
        return [
            "[FILENAME] No closing tag\nContent",
            "No opening tag [/TITLE]\nContent",
            "[FILENAME][/FILENAME]\nEmpty title",
            "Regular text without any tags",
        ]


class EnhancedChunkProcessorFactory:
    """Factory for creating EnhancedChunkProcessor instances"""

    @staticmethod
    def create_processor() -> EnhancedChunkProcessor:
        """Create processor with standard service"""
        service = TitleInjectionServiceFactory.create_service()
        return EnhancedChunkProcessor(service)

    @staticmethod
    def create_custom_processor(
        service: TitleInjectionService,
    ) -> EnhancedChunkProcessor:
        """Create processor with custom service"""
        return EnhancedChunkProcessor(service)


class TestTitleInjectionService:
    """Test the core title injection functionality using factory patterns"""

    def test_inject_titles_with_title(self):
        """Test title injection when title is present"""
        service = TitleInjectionServiceFactory.create_service()
        document = DocumentDataFactory.create_simple_document()

        result = service.inject_titles([document["content"]], [document["metadata"]])

        expected = (
            "[FILENAME] Introduction to AI [/FILENAME]\nThis is some content about AI."
        )
        assert result[0] == expected

    def test_inject_titles_no_title(self):
        """Test behavior when no title is provided"""
        service = TitleInjectionServiceFactory.create_service()
        document = DocumentDataFactory.create_document_without_title()

        result = service.inject_titles([document["content"]], [document["metadata"]])

        assert result[0] == "Content without title."

    def test_inject_titles_empty_title(self):
        """Test behavior with empty title"""
        service = TitleInjectionServiceFactory.create_service()
        document = DocumentDataFactory.create_document_with_empty_title()

        result = service.inject_titles([document["content"]], [document["metadata"]])

        assert result[0] == "Some content."

    def test_inject_titles_multiple_documents(self):
        """Test title injection with multiple documents"""
        service = TitleInjectionServiceFactory.create_service()
        documents = DocumentDataFactory.create_multiple_documents()

        texts = [doc["content"] for doc in documents]
        metadata = [doc["metadata"] for doc in documents]
        results = service.inject_titles(texts, metadata)

        assert len(results) == 3
        assert (
            results[0] == "[FILENAME] Document One [/FILENAME]\nFirst document content."
        )
        assert results[1] == "Second document content."  # No change
        assert (
            results[2]
            == "[FILENAME] Document Three [/FILENAME]\nThird document content."
        )

    def test_extract_title_various_keys(self):
        """Test title extraction from different metadata keys"""
        service = TitleInjectionServiceFactory.create_service()
        test_cases = MetadataTestDataFactory.create_title_extraction_test_cases()

        for metadata, expected in test_cases:
            result = service._extract_title(metadata)
            assert result == expected

    def test_extract_title_from_enhanced_text(self):
        """Test extracting title from enhanced text"""
        service = TitleInjectionServiceFactory.create_service()
        enhanced_text = TextDataFactory.create_enhanced_text()

        result = service.extract_title_from_enhanced_text(enhanced_text)

        assert result == "Test Title"

    def test_extract_title_from_plain_text(self):
        """Test extracting title from plain text (should return None)"""
        service = TitleInjectionServiceFactory.create_service()
        plain_text = TextDataFactory.create_plain_text()

        result = service.extract_title_from_enhanced_text(plain_text)

        assert result is None

    def test_remove_title_injection(self):
        """Test removing title injection to get original content"""
        service = TitleInjectionServiceFactory.create_service()
        enhanced_text = TextDataFactory.create_enhanced_text()

        result = service.remove_title_injection(enhanced_text)

        assert result == "Some content here."

    def test_remove_title_injection_no_title(self):
        """Test removing title injection from text without title"""
        service = TitleInjectionServiceFactory.create_service()
        plain_text = TextDataFactory.create_plain_text()

        result = service.remove_title_injection(plain_text)

        assert result == plain_text

    def test_custom_tokens(self):
        """Test title injection with custom tokens"""
        service = TitleInjectionServiceFactory.create_custom_service()

        # Use specific document content and title for this test
        texts = ["Content here."]
        metadata = [{"title": "Custom Title"}]

        result = service.inject_titles(texts, metadata)

        expected = "<TITLE> Custom Title </TITLE> | Content here."
        assert result[0] == expected

    def test_filename_title_extraction(self):
        """Test enhanced title extraction from filenames"""
        service = TitleInjectionServiceFactory.create_service()
        test_cases = MetadataTestDataFactory.create_filename_test_cases()

        for metadata, expected in test_cases:
            result = service._extract_title(metadata)
            assert (
                result == expected
            ), f"Failed for {metadata}, got {result}, expected {expected}"

    def test_is_filename(self):
        """Test filename detection logic"""
        service = TitleInjectionServiceFactory.create_service()
        test_cases = MetadataTestDataFactory.create_filename_detection_cases()

        for text, expected in test_cases:
            result = service._is_filename(text)
            assert (
                result == expected
            ), f"Failed for '{text}', got {result}, expected {expected}"

    def test_extract_title_from_filename(self):
        """Test direct filename to title conversion"""
        service = TitleInjectionServiceFactory.create_service()
        test_cases = MetadataTestDataFactory.create_filename_conversion_cases()

        for filename, expected in test_cases:
            result = service._extract_title_from_filename(filename)
            assert (
                result == expected
            ), f"Failed for '{filename}', got {result}, expected {expected}"

    def test_clean_filename_patterns(self):
        """Test filename pattern cleaning"""
        service = TitleInjectionServiceFactory.create_service()
        test_cases = MetadataTestDataFactory.create_pattern_cleaning_cases()

        for input_text, expected in test_cases:
            result = service._clean_filename_patterns(input_text)
            assert (
                result == expected
            ), f"Failed for '{input_text}', got {result}, expected {expected}"


class TestEnhancedChunkProcessor:
    """Test the document processing with title injection using factory patterns"""

    def test_process_documents_for_embedding(self):
        """Test processing documents for embedding with title injection"""
        processor = EnhancedChunkProcessorFactory.create_processor()
        documents = DocumentDataFactory.create_documents_for_embedding()

        result = processor.process_documents_for_embedding(documents)

        assert len(result) == 2

        # First document
        assert (
            result[0]["content"]
            == "[FILENAME] ML Basics [/FILENAME]\nThis is about machine learning."
        )
        assert result[0]["original_content"] == "This is about machine learning."
        assert result[0]["metadata"]["author"] == "John Doe"

        # Second document - filename should be processed to clean title
        assert (
            result[1]["content"]
            == "[FILENAME] Deep Learning [/FILENAME]\nDeep learning fundamentals."
        )
        assert result[1]["original_content"] == "Deep learning fundamentals."

    def test_prepare_for_dual_indexing(self):
        """Test preparing documents for dual indexing (Pinecone + Elasticsearch)"""
        processor = EnhancedChunkProcessorFactory.create_processor()
        documents = [DocumentDataFactory.create_document_for_dual_indexing()]

        result = processor.prepare_for_dual_indexing(documents)

        assert "dense" in result
        assert "sparse" in result
        assert len(result["dense"]) == 1
        assert len(result["sparse"]) == 1

        # Dense version (for Pinecone) - enhanced content
        dense_doc = result["dense"][0]
        assert (
            dense_doc["content"]
            == "[FILENAME] AI Safety Guide [/FILENAME]\nContent about AI safety."
        )

        # Sparse version (for Elasticsearch) - separate title field
        sparse_doc = result["sparse"][0]
        assert sparse_doc["content"] == "Content about AI safety."  # Original content
        assert sparse_doc["title"] == "AI Safety Guide"  # Separate title field

    def test_prepare_for_dual_indexing_no_title(self):
        """Test dual indexing preparation when no title is present"""
        processor = EnhancedChunkProcessorFactory.create_processor()
        documents = [DocumentDataFactory.create_document_without_title()]

        result = processor.prepare_for_dual_indexing(documents)

        # Dense version - no enhancement
        dense_doc = result["dense"][0]
        assert dense_doc["content"] == "Content without title."

        # Sparse version - empty title
        sparse_doc = result["sparse"][0]
        assert sparse_doc["content"] == "Content without title."
        assert sparse_doc["title"] == ""


class TestTitleInjectionEdgeCases:
    """Test edge cases and error handling using factory patterns"""

    def test_inject_titles_mismatched_lengths(self):
        """Test with mismatched text and metadata lengths"""
        service = TitleInjectionServiceFactory.create_service()

        texts = ["Content one.", "Content two."]
        metadata = [{"title": "Title One"}]  # One less metadata entry

        # Should handle gracefully - will process only matching pairs
        result = service.inject_titles(texts, metadata)
        assert len(result) == 1  # Only processes the first item that has metadata

    def test_inject_titles_empty_inputs(self):
        """Test with empty inputs"""
        service = TitleInjectionServiceFactory.create_service()

        texts = []
        metadata = []

        result = service.inject_titles(texts, metadata)

        assert result == []

    def test_unicode_title_handling(self):
        """Test handling of unicode characters in titles"""
        service = TitleInjectionServiceFactory.create_service()
        document = DocumentDataFactory.create_document_with_unicode()

        result = service.inject_titles([document["content"]], [document["metadata"]])

        expected = (
            "[FILENAME] Título con acentos 中文 🚀 [/FILENAME]\nContent with unicode."
        )
        assert result[0] == expected

    def test_very_long_title(self):
        """Test handling of very long titles"""
        service = TitleInjectionServiceFactory.create_service()
        document = DocumentDataFactory.create_document_with_long_title()

        result = service.inject_titles([document["content"]], [document["metadata"]])

        long_title = "A" * 1000
        assert long_title in result[0]
        assert "Short content." in result[0]

    def test_malformed_enhanced_text_extraction(self):
        """Test extracting title from malformed enhanced text"""
        service = TitleInjectionServiceFactory.create_service()
        malformed_cases = TextDataFactory.create_malformed_texts()

        for text in malformed_cases:
            result = service.extract_title_from_enhanced_text(text)
            # Should handle gracefully, might return None or empty string
            assert isinstance(result, str | type(None))

    def test_factory_consistency(self):
        """Test that factories create consistent objects"""
        # Test service factory
        service1 = TitleInjectionServiceFactory.create_service()
        service2 = TitleInjectionServiceFactory.create_service()
        assert isinstance(service1, TitleInjectionService)
        assert isinstance(service2, TitleInjectionService)

        # Test custom service
        custom_service = TitleInjectionServiceFactory.create_custom_service()
        assert isinstance(custom_service, TitleInjectionService)

        # Test processor factory
        processor = EnhancedChunkProcessorFactory.create_processor()
        assert isinstance(processor, EnhancedChunkProcessor)

        # Test document factory
        document = DocumentDataFactory.create_simple_document()
        assert "content" in document
        assert "metadata" in document
        assert "title" in document["metadata"]

    def test_metadata_factory_completeness(self):
        """Test that metadata factories provide comprehensive test data"""
        title_cases = MetadataTestDataFactory.create_title_extraction_test_cases()
        filename_cases = MetadataTestDataFactory.create_filename_test_cases()
        detection_cases = MetadataTestDataFactory.create_filename_detection_cases()

        assert len(title_cases) >= 10  # Comprehensive test cases
        assert len(filename_cases) >= 10  # Comprehensive filename tests
        assert len(detection_cases) >= 5  # Basic detection tests

        # Verify structure
        for metadata, expected in title_cases[:3]:  # Test first few
            assert isinstance(metadata, dict)
            assert expected is None or isinstance(expected, str)
