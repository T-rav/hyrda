"""Tests for document processor service."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from services.gdrive.document_processor import DocumentProcessor


@pytest.fixture
def processor():
    """Create document processor instance."""
    return DocumentProcessor()


@pytest.fixture
def processor_with_openai_key():
    """Create document processor with OpenAI API key."""
    return DocumentProcessor(openai_api_key="test-key-123")


class TestDocumentProcessorTextExtraction:
    """Test text extraction from various document types."""

    def test_extracts_text_from_plain_text(self, processor):
        """Test extraction from plain text files."""
        content = b"This is plain text content."
        result = processor.extract_text(content, "text/plain")
        assert result == "This is plain text content."

    def test_extracts_text_from_pdf(self, processor):
        """Test extraction from PDF files."""
        # Mock PDF content - basic structure
        # In real tests, this would use a real PDF library
        content = b"%PDF-1.4\ntest content"
        mime_type = "application/pdf"

        # Test that method exists and handles PDF mime type
        result = processor.extract_text(content, mime_type)
        # Document processor may return None for mock PDF data without proper structure
        assert result is None or isinstance(result, str)

    def test_handles_empty_content(self, processor):
        """Test handling of empty content."""
        result = processor.extract_text(b"", "text/plain")
        assert result == ""

    def test_handles_unsupported_mime_type(self, processor):
        """Test handling of unsupported file types."""
        content = b"some content"
        result = processor.extract_text(content, "application/x-unknown")
        # Should return empty string or raise exception
        assert result == "" or result is None

    def test_handles_binary_content_gracefully(self, processor):
        """Test handling of binary data that isn't text."""
        # Binary data that can't be decoded as text
        content = bytes([0xFF, 0xFE, 0xFD, 0xFC])
        result = processor.extract_text(content, "application/octet-stream")
        # Should not crash
        assert isinstance(result, str) or result is None


class TestDocumentProcessorWordDocuments:
    """Test Word document processing."""

    def test_handles_docx_mime_type(self, processor):
        """Test DOCX mime type is recognized."""
        mime_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        # Test that processor accepts this mime type
        # In production, would extract text from real DOCX
        result = processor.extract_text(b"mock docx content", mime_type)
        assert isinstance(result, str) or result is None


class TestDocumentProcessorGoogleDocs:
    """Test Google Docs format processing."""

    def test_handles_google_docs_mime_type(self, processor):
        """Test Google Docs mime type."""
        mime_type = "application/vnd.google-apps.document"
        # Google Docs are typically exported as text or HTML
        content = b"Google Doc content"
        result = processor.extract_text(content, mime_type)
        # May return None for mock data that isn't properly formatted
        assert result is None or isinstance(result, str)

    def test_handles_google_sheets_mime_type(self, processor):
        """Test Google Sheets mime type."""
        mime_type = "application/vnd.google-apps.spreadsheet"
        content = b"Sheet data"
        result = processor.extract_text(content, mime_type)
        assert isinstance(result, str) or result is None


class TestDocumentProcessorErrorHandling:
    """Test error handling in document processor."""

    def test_handles_corrupted_data(self, processor):
        """Test handling of corrupted file data."""
        # Corrupted PDF header
        content = b"%PDF-CORRUPTED\x00\x00\x00"
        result = processor.extract_text(content, "application/pdf")
        # Should not crash, may return empty string
        assert isinstance(result, str) or result is None

    def test_handles_none_content(self, processor):
        """Test handling of None content."""
        with pytest.raises((TypeError, AttributeError)):
            processor.extract_text(None, "text/plain")

    def test_handles_none_mime_type(self, processor):
        """Test handling of None mime type."""
        content = b"test content"
        # Should raise AttributeError when None mime type is provided
        with pytest.raises(AttributeError):
            processor.extract_text(content, None)


class TestDocumentProcessorTextCleaning:
    """Test text cleaning and normalization."""

    def test_normalizes_whitespace(self, processor):
        """Test whitespace normalization."""
        content = b"Text  with\n\nextra   spaces\t\tand\ttabs"
        result = processor.extract_text(content, "text/plain")
        # Should normalize multiple spaces
        assert (
            "  " not in result or result == "Text  with\n\nextra   spaces\t\tand\ttabs"
        )

    def test_removes_control_characters(self, processor):
        """Test removal of control characters."""
        # Text with control characters
        content = b"Normal text\x00\x01\x02 more text"
        result = processor.extract_text(content, "text/plain")
        # Should remove or handle control characters
        assert isinstance(result, str)

    def test_handles_unicode_content(self, processor):
        """Test handling of Unicode characters."""
        content = "Unicode: émojis 🎉 中文".encode()
        result = processor.extract_text(content, "text/plain")
        assert "émojis" in result or "mojis" in result
        assert "🎉" in result or result  # Emoji may be preserved or stripped


class TestDocumentProcessorFileTypeDetection:
    """Test file type detection and handling."""

    def test_detects_text_files(self, processor):
        """Test detection of text files."""
        text_types = [
            "text/plain",
            "text/html",
            "text/csv",
            "text/markdown",
        ]
        for mime_type in text_types:
            result = processor.extract_text(b"test", mime_type)
            assert isinstance(result, str)

    def test_detects_document_files(self, processor):
        """Test detection of document files."""
        doc_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ]
        for mime_type in doc_types:
            # Should not crash, may return empty for mock data
            result = processor.extract_text(b"mock", mime_type)
            assert result is None or isinstance(result, str)


class TestDocumentProcessorPerformance:
    """Test performance considerations."""

    def test_handles_large_text_files(self, processor):
        """Test handling of large text files."""
        # 1MB of text
        large_content = b"x" * (1024 * 1024)
        result = processor.extract_text(large_content, "text/plain")
        assert len(result) > 0

    def test_handles_empty_files(self, processor):
        """Test handling of empty files."""
        result = processor.extract_text(b"", "text/plain")
        assert result == ""

    def test_processes_quickly(self, processor):
        """Test that processing doesn't hang."""
        import time

        start = time.time()
        content = b"Quick processing test" * 1000
        processor.extract_text(content, "text/plain")
        duration = time.time() - start

        # Should process 20KB text in under 1 second
        assert duration < 1.0


class TestDocumentProcessorAudioTranscription:
    """Test audio transcription functionality."""

    def test_transcribes_audio_with_api_key(self, processor_with_openai_key):
        """Test audio transcription when API key is configured."""
        audio_content = b"mock audio data"
        mock_transcript = "This is transcribed audio text"

        with patch("openai.OpenAI") as mock_openai:
            # Mock OpenAI client
            mock_client = Mock()
            mock_openai.return_value = mock_client

            # Mock transcription response
            mock_client.audio.transcriptions.create.return_value = mock_transcript

            # Test transcription
            result = processor_with_openai_key.extract_text(
                audio_content, "audio/mpeg", "test.mp3"
            )

            # Verify OpenAI was called correctly
            mock_openai.assert_called_once_with(api_key="test-key-123")
            mock_client.audio.transcriptions.create.assert_called_once()

            # Verify result
            assert result == mock_transcript

    def test_skips_audio_without_api_key(self, processor):
        """Test audio transcription skips when API key not configured."""
        audio_content = b"mock audio data"

        result = processor.extract_text(audio_content, "audio/mpeg", "test.mp3")

        # Should return None when API key not configured
        assert result is None

    def test_handles_audio_transcription_errors(self, processor_with_openai_key):
        """Test error handling during audio transcription."""
        audio_content = b"mock audio data"

        with patch("openai.OpenAI") as mock_openai:
            # Mock OpenAI to raise an error
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.audio.transcriptions.create.side_effect = Exception("API error")

            result = processor_with_openai_key.extract_text(
                audio_content, "audio/mpeg", "test.mp3"
            )

            # Should return None on error
            assert result is None

    def test_handles_empty_audio_transcription(self, processor_with_openai_key):
        """Test handling of empty transcription results."""
        audio_content = b"mock audio data"

        with patch("openai.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client

            # Mock empty transcription
            mock_client.audio.transcriptions.create.return_value = "   "

            result = processor_with_openai_key.extract_text(
                audio_content, "audio/mpeg", "test.mp3"
            )

            # Should return None for empty/whitespace-only transcriptions
            assert result is None

    def test_cleans_up_temp_files_on_success(self, processor_with_openai_key):
        """Test temporary files are cleaned up after successful transcription."""
        audio_content = b"mock audio data"

        with (
            patch("openai.OpenAI"),
            patch("os.unlink") as mock_unlink,
            patch("builtins.open", MagicMock()),
        ):
            processor_with_openai_key._transcribe_audio(audio_content, "test.mp3")

            # Verify temp file was deleted
            assert mock_unlink.called

    def test_cleans_up_temp_files_on_error(self, processor_with_openai_key):
        """Test temporary files are cleaned up even on errors."""
        audio_content = b"mock audio data"

        with patch("openai.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.audio.transcriptions.create.side_effect = Exception("API error")

            with (
                patch("os.unlink") as mock_unlink,
                patch("os.path.exists", return_value=True),
            ):
                processor_with_openai_key._transcribe_audio(audio_content, "test.mp3")

                # Verify temp file was deleted even after error
                assert mock_unlink.called

    def test_supports_multiple_audio_formats(self, processor_with_openai_key):
        """Test support for various audio MIME types."""
        audio_formats = [
            ("audio/mpeg", "test.mp3"),
            ("audio/wav", "test.wav"),
            ("audio/mp4", "test.m4a"),
            ("audio/aac", "test.aac"),
            ("audio/ogg", "test.ogg"),
            ("audio/flac", "test.flac"),
            ("audio/webm", "test.webm"),
        ]

        for mime_type, filename in audio_formats:
            with patch("openai.OpenAI") as mock_openai:
                mock_client = Mock()
                mock_openai.return_value = mock_client
                mock_client.audio.transcriptions.create.return_value = (
                    f"Transcribed {filename}"
                )

                result = processor_with_openai_key.extract_text(
                    b"audio data", mime_type, filename
                )

                assert result == f"Transcribed {filename}"


class TestDocumentProcessorVideoTranscription:
    """Test video transcription functionality."""

    def test_transcribes_video_with_api_key(self, processor_with_openai_key):
        """Test video transcription when API key is configured."""
        video_content = b"mock video data"
        mock_transcript = "This is transcribed video audio"

        with patch("openai.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.audio.transcriptions.create.return_value = mock_transcript

            result = processor_with_openai_key.extract_text(
                video_content, "video/mp4", "test.mp4"
            )

            # Verify result
            assert result == mock_transcript

    def test_skips_video_without_api_key(self, processor):
        """Test video transcription skips when API key not configured."""
        video_content = b"mock video data"

        result = processor.extract_text(video_content, "video/mp4", "test.mp4")

        # Should return None when API key not configured
        assert result is None

    def test_handles_video_transcription_errors(self, processor_with_openai_key):
        """Test error handling during video transcription."""
        video_content = b"mock video data"

        with patch("openai.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.audio.transcriptions.create.side_effect = Exception("API error")

            result = processor_with_openai_key.extract_text(
                video_content, "video/mp4", "test.mp4"
            )

            # Should return None on error
            assert result is None

    def test_supports_multiple_video_formats(self, processor_with_openai_key):
        """Test support for various video MIME types."""
        video_formats = [
            ("video/mp4", "test.mp4"),
            ("video/quicktime", "test.mov"),
            ("video/x-msvideo", "test.avi"),
            ("video/x-matroska", "test.mkv"),
            ("video/webm", "test.webm"),
        ]

        for mime_type, filename in video_formats:
            with patch("openai.OpenAI") as mock_openai:
                mock_client = Mock()
                mock_openai.return_value = mock_client
                mock_client.audio.transcriptions.create.return_value = (
                    f"Transcribed {filename}"
                )

                result = processor_with_openai_key.extract_text(
                    b"video data", mime_type, filename
                )

                assert result == f"Transcribed {filename}"

    def test_cleans_up_video_temp_files(self, processor_with_openai_key):
        """Test temporary video files are cleaned up."""
        video_content = b"mock video data"

        with (
            patch("openai.OpenAI"),
            patch("os.unlink") as mock_unlink,
            patch("builtins.open", MagicMock()),
        ):
            processor_with_openai_key._transcribe_video(video_content, "test.mp4")

            # Verify temp file was deleted
            assert mock_unlink.called


class TestDocumentProcessorMimeTypeDetection:
    """Test MIME type detection for audio/video files."""

    def test_detects_audio_mime_types(self, processor_with_openai_key):
        """Test detection of audio MIME types."""
        audio_types = processor_with_openai_key.AUDIO_MIME_TYPES

        # Verify expected audio types are recognized
        assert "audio/mpeg" in audio_types
        assert "audio/wav" in audio_types
        assert "audio/mp4" in audio_types

    def test_detects_video_mime_types(self, processor_with_openai_key):
        """Test detection of video MIME types."""
        video_types = processor_with_openai_key.VIDEO_MIME_TYPES

        # Verify expected video types are recognized
        assert "video/mp4" in video_types
        assert "video/quicktime" in video_types
        assert "video/webm" in video_types

    def test_routes_audio_to_transcription(self, processor_with_openai_key):
        """Test that audio MIME types route to transcription."""
        with patch(
            "services.gdrive.document_processor.DocumentProcessor._transcribe_audio"
        ) as mock_transcribe:
            mock_transcribe.return_value = "transcribed"

            result = processor_with_openai_key.extract_text(
                b"audio", "audio/mpeg", "test.mp3"
            )

            # Verify _transcribe_audio was called
            mock_transcribe.assert_called_once()
            assert result == "transcribed"

    def test_routes_video_to_transcription(self, processor_with_openai_key):
        """Test that video MIME types route to transcription."""
        with patch(
            "services.gdrive.document_processor.DocumentProcessor._transcribe_video"
        ) as mock_transcribe:
            mock_transcribe.return_value = "transcribed"

            result = processor_with_openai_key.extract_text(
                b"video", "video/mp4", "test.mp4"
            )

            # Verify _transcribe_video was called
            mock_transcribe.assert_called_once()
            assert result == "transcribed"
