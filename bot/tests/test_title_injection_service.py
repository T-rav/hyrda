"""
Tests for Title Injection Service

Validates title injection logic for enhanced RAG embeddings
"""

from services.title_injection_service import (
    EnhancedChunkProcessor,
    TitleInjectionService,
)


class TestTitleInjectionService:
    """Test the core title injection functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.service = TitleInjectionService()
        self.processor = EnhancedChunkProcessor(self.service)

    def test_inject_titles_with_title(self):
        """Test title injection when title is present"""
        texts = ["This is some content about AI."]
        metadata = [{"title": "Introduction to AI"}]

        result = self.service.inject_titles(texts, metadata)

        expected = "[TITLE] Introduction to AI [/TITLE]\nThis is some content about AI."
        assert result[0] == expected

    def test_inject_titles_no_title(self):
        """Test behavior when no title is provided"""
        texts = ["Content without title."]
        metadata = [{}]

        result = self.service.inject_titles(texts, metadata)

        assert result[0] == "Content without title."

    def test_inject_titles_empty_title(self):
        """Test behavior with empty title"""
        texts = ["Some content."]
        metadata = [{"title": ""}]

        result = self.service.inject_titles(texts, metadata)

        assert result[0] == "Some content."

    def test_inject_titles_multiple_documents(self):
        """Test title injection with multiple documents"""
        texts = [
            "First document content.",
            "Second document content.",
            "Third document content.",
        ]
        metadata = [
            {"title": "Document One"},
            {},  # No title
            {"title": "Document Three"},
        ]

        results = self.service.inject_titles(texts, metadata)

        assert len(results) == 3
        assert results[0] == "[TITLE] Document One [/TITLE]\nFirst document content."
        assert results[1] == "Second document content."  # No change
        assert results[2] == "[TITLE] Document Three [/TITLE]\nThird document content."

    def test_extract_title_various_keys(self):
        """Test title extraction from different metadata keys"""
        test_cases = [
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

        for metadata, expected in test_cases:
            result = self.service._extract_title(metadata)
            assert result == expected

    def test_extract_title_from_enhanced_text(self):
        """Test extracting title from enhanced text"""
        enhanced_text = "[TITLE] Test Title [/TITLE]\nSome content here."

        result = self.service.extract_title_from_enhanced_text(enhanced_text)

        assert result == "Test Title"

    def test_extract_title_from_plain_text(self):
        """Test extracting title from plain text (should return None)"""
        plain_text = "Just some regular content without title tags."

        result = self.service.extract_title_from_enhanced_text(plain_text)

        assert result is None

    def test_remove_title_injection(self):
        """Test removing title injection to get original content"""
        enhanced_text = "[TITLE] Test Title [/TITLE]\nOriginal content here."

        result = self.service.remove_title_injection(enhanced_text)

        assert result == "Original content here."

    def test_remove_title_injection_no_title(self):
        """Test removing title injection from text without title"""
        plain_text = "Just regular content."

        result = self.service.remove_title_injection(plain_text)

        assert result == "Just regular content."

    def test_custom_tokens(self):
        """Test title injection with custom tokens"""
        service = TitleInjectionService(
            title_start_token="<TITLE>", title_end_token="</TITLE>", separator=" | "
        )

        texts = ["Content here."]
        metadata = [{"title": "Custom Title"}]

        result = service.inject_titles(texts, metadata)

        expected = "<TITLE> Custom Title </TITLE> | Content here."
        assert result[0] == expected

    def test_filename_title_extraction(self):
        """Test enhanced title extraction from filenames"""
        test_cases = [
            # Basic PDF files
            ({"file_name": "Apple - Project Details File.pdf"}, "Project Details File"),
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
                "Azure Documentation",
            ),
            (
                {"file_name": "Google - Cloud Security Guide.docx"},
                "Cloud Security Guide",
            ),
            ({"file_name": "Slack - API Reference.pdf"}, "API Reference"),
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

        for metadata, expected in test_cases:
            result = self.service._extract_title(metadata)
            assert result == expected, (
                f"Failed for {metadata}, got {result}, expected {expected}"
            )

    def test_is_filename(self):
        """Test filename detection logic"""
        test_cases = [
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

        for text, expected in test_cases:
            result = self.service._is_filename(text)
            assert result == expected, (
                f"Failed for '{text}', got {result}, expected {expected}"
            )

    def test_extract_title_from_filename(self):
        """Test direct filename to title conversion"""
        test_cases = [
            ("Apple - Project Details File.pdf", "Project Details File"),
            ("Machine_Learning_Guide.pdf", "Machine Learning Guide"),
            ("quarterly-report-2023.docx", "Quarterly Report 2023"),
            ("API_REFERENCE_v2.1.pdf", "API Reference V2.1"),
            ("ml_basics.txt", "ML Basics"),
            ("user_interface_design.pptx", "User Interface Design"),
            ("simple.pdf", "Simple"),
            ("a.pdf", "a.pdf"),  # Too short, keep original
        ]

        for filename, expected in test_cases:
            result = self.service._extract_title_from_filename(filename)
            assert result == expected, (
                f"Failed for '{filename}', got {result}, expected {expected}"
            )

    def test_clean_filename_patterns(self):
        """Test filename pattern cleaning"""
        test_cases = [
            ("Apple - Project Details File", "Project Details File"),
            ("Microsoft - Azure Documentation", "Azure Documentation"),
            ("user_manual_v2", "User Manual V2"),
            ("API_REFERENCE_final", "API Reference Final"),
            ("machine_learning_guide", "Machine Learning Guide"),
            ("quarterly  report   2023", "Quarterly Report 2023"),
            ("ai_ml_basics", "AI ML Basics"),
            ("ios_development", "iOS Development"),
            ("json_api_guide", "JSON API Guide"),
        ]

        for input_text, expected in test_cases:
            result = self.service._clean_filename_patterns(input_text)
            assert result == expected, (
                f"Failed for '{input_text}', got {result}, expected {expected}"
            )


class TestEnhancedChunkProcessor:
    """Test the document processing with title injection"""

    def setup_method(self):
        """Set up test fixtures"""
        self.service = TitleInjectionService()
        self.processor = EnhancedChunkProcessor(self.service)

    def test_process_documents_for_embedding(self):
        """Test processing documents for embedding with title injection"""
        documents = [
            {
                "content": "This is about machine learning.",
                "metadata": {"title": "ML Basics", "author": "John Doe"},
            },
            {
                "content": "Deep learning fundamentals.",
                "metadata": {"filename": "deep_learning.pdf"},
            },
        ]

        result = self.processor.process_documents_for_embedding(documents)

        assert len(result) == 2

        # First document
        assert (
            result[0]["content"]
            == "[TITLE] ML Basics [/TITLE]\nThis is about machine learning."
        )
        assert result[0]["original_content"] == "This is about machine learning."
        assert result[0]["metadata"]["author"] == "John Doe"

        # Second document - filename should be processed to clean title
        assert (
            result[1]["content"]
            == "[TITLE] Deep Learning [/TITLE]\nDeep learning fundamentals."
        )
        assert result[1]["original_content"] == "Deep learning fundamentals."

    def test_prepare_for_dual_indexing(self):
        """Test preparing documents for dual indexing (Pinecone + Elasticsearch)"""
        documents = [
            {
                "content": "Content about AI safety.",
                "metadata": {"title": "AI Safety Guide", "category": "safety"},
            }
        ]

        result = self.processor.prepare_for_dual_indexing(documents)

        assert "dense" in result
        assert "sparse" in result
        assert len(result["dense"]) == 1
        assert len(result["sparse"]) == 1

        # Dense version (for Pinecone) - enhanced content
        dense_doc = result["dense"][0]
        assert (
            dense_doc["content"]
            == "[TITLE] AI Safety Guide [/TITLE]\nContent about AI safety."
        )

        # Sparse version (for Elasticsearch) - separate title field
        sparse_doc = result["sparse"][0]
        assert sparse_doc["content"] == "Content about AI safety."  # Original content
        assert sparse_doc["title"] == "AI Safety Guide"  # Separate title field

    def test_prepare_for_dual_indexing_no_title(self):
        """Test dual indexing preparation when no title is present"""
        documents = [
            {
                "content": "Some content without title.",
                "metadata": {"author": "Jane Smith"},
            }
        ]

        result = self.processor.prepare_for_dual_indexing(documents)

        # Dense version - no enhancement
        dense_doc = result["dense"][0]
        assert dense_doc["content"] == "Some content without title."

        # Sparse version - empty title
        sparse_doc = result["sparse"][0]
        assert sparse_doc["content"] == "Some content without title."
        assert sparse_doc["title"] == ""


class TestTitleInjectionEdgeCases:
    """Test edge cases and error handling"""

    def setup_method(self):
        self.service = TitleInjectionService()

    def test_inject_titles_mismatched_lengths(self):
        """Test with mismatched text and metadata lengths"""
        texts = ["Content one.", "Content two."]
        metadata = [{"title": "Title One"}]  # One less metadata entry

        # Should handle gracefully - will process only matching pairs
        result = self.service.inject_titles(texts, metadata)
        assert len(result) == 1  # Only processes the first item that has metadata

    def test_inject_titles_empty_inputs(self):
        """Test with empty inputs"""
        texts = []
        metadata = []

        result = self.service.inject_titles(texts, metadata)

        assert result == []

    def test_unicode_title_handling(self):
        """Test handling of unicode characters in titles"""
        texts = ["Content with unicode."]
        metadata = [{"title": "Título con acentos 中文 🚀"}]

        result = self.service.inject_titles(texts, metadata)

        expected = "[TITLE] Título con acentos 中文 🚀 [/TITLE]\nContent with unicode."
        assert result[0] == expected

    def test_very_long_title(self):
        """Test handling of very long titles"""
        long_title = "A" * 1000  # 1000 character title
        texts = ["Short content."]
        metadata = [{"title": long_title}]

        result = self.service.inject_titles(texts, metadata)

        assert long_title in result[0]
        assert "Short content." in result[0]

    def test_malformed_enhanced_text_extraction(self):
        """Test extracting title from malformed enhanced text"""
        malformed_cases = [
            "[TITLE] No closing tag\nContent",
            "No opening tag [/TITLE]\nContent",
            "[TITLE][/TITLE]\nEmpty title",
            "Regular text without any tags",
        ]

        for text in malformed_cases:
            result = self.service.extract_title_from_enhanced_text(text)
            # Should handle gracefully, might return None or empty string
            assert isinstance(result, str | type(None))
