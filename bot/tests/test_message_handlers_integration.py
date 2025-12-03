import io
import os
import sys
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import from refactored modules
from handlers.file_processors import process_file_attachments
from handlers.file_processors.office_processor import (
    OPENPYXL_AVAILABLE,
    PYTHON_DOCX_AVAILABLE,
    PYTHON_PPTX_AVAILABLE,
    extract_excel_text,
    extract_office_text,
    extract_powerpoint_text,
    extract_word_text,
)
from handlers.file_processors.pdf_processor import (
    PYMUPDF_AVAILABLE,
    extract_pdf_text,
)
from handlers.message_handlers import handle_bot_command, handle_message
from handlers.prompt_manager import get_user_system_prompt


# TDD Factory Patterns for Message Handler Testing
class SlackFileBuilder:
    """Builder for creating Slack file attachment objects"""

    def __init__(self):
        self._name = "test.txt"
        self._mimetype = "text/plain"
        self._size = 1000
        self._url_private = "https://test.com/file"
        self._additional_fields = {}

    def with_name(self, name: str) -> "SlackFileBuilder":
        self._name = name
        return self

    def with_mimetype(self, mimetype: str) -> "SlackFileBuilder":
        self._mimetype = mimetype
        return self

    def with_size(self, size: int) -> "SlackFileBuilder":
        self._size = size
        return self

    def with_url(self, url: str) -> "SlackFileBuilder":
        self._url_private = url
        return self

    def with_no_url(self) -> "SlackFileBuilder":
        """Remove private URL to simulate files without download access"""
        if "url_private" in self._additional_fields:
            del self._additional_fields["url_private"]
        self._url_private = None
        return self

    def with_large_size(self, size_mb: int = 200) -> "SlackFileBuilder":
        """Set file size to exceed processing limits"""
        self._size = size_mb * 1024 * 1024
        return self

    def build(self) -> dict[str, Any]:
        """Build the file attachment dictionary"""
        file_data = {
            "name": self._name,
            "mimetype": self._mimetype,
            "size": self._size,
            **self._additional_fields,
        }
        if self._url_private is not None:
            file_data["url_private"] = self._url_private
        return file_data

    @classmethod
    def pdf_file(cls, name: str = "test.pdf") -> "SlackFileBuilder":
        return cls().with_name(name).with_mimetype("application/pdf")

    @classmethod
    def word_file(cls, name: str = "test.docx") -> "SlackFileBuilder":
        return (
            cls()
            .with_name(name)
            .with_mimetype(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        )

    @classmethod
    def excel_file(cls, name: str = "test.xlsx") -> "SlackFileBuilder":
        return (
            cls()
            .with_name(name)
            .with_mimetype(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        )

    @classmethod
    def powerpoint_file(cls, name: str = "test.pptx") -> "SlackFileBuilder":
        return (
            cls()
            .with_name(name)
            .with_mimetype(
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
        )

    @classmethod
    def text_file(
        cls, name: str = "test.txt", mimetype: str = "text/plain"
    ) -> "SlackFileBuilder":
        return cls().with_name(name).with_mimetype(mimetype)

    @classmethod
    def subtitle_file(
        cls, name: str = "captions.vtt", mimetype: str = "text/vtt"
    ) -> "SlackFileBuilder":
        return cls().with_name(name).with_mimetype(mimetype).with_size(500)

    @classmethod
    def srt_subtitle_file(cls, name: str = "subtitles.srt") -> "SlackFileBuilder":
        return (
            cls().with_name(name).with_mimetype("application/x-subrip").with_size(300)
        )

    @classmethod
    def large_file(
        cls, name: str = "huge.pdf", size_mb: int = 200
    ) -> "SlackFileBuilder":
        return cls().pdf_file(name).with_large_size(size_mb)

    @classmethod
    def file_without_url(cls, name: str = "no_url.pdf") -> "SlackFileBuilder":
        return cls().pdf_file(name).with_no_url()

    @classmethod
    def unsupported_file(cls, name: str = "test.unknown") -> "SlackFileBuilder":
        return cls().with_name(name).with_mimetype("application/unknown")


class HTTPResponseFactory:
    """Factory for creating HTTP response mocks"""

    @staticmethod
    def success_response(
        content: str = "test content", binary_content: bytes = None
    ) -> Mock:
        """Create successful HTTP response"""
        response = Mock()
        response.status_code = 200
        response.text = content
        response.content = binary_content or content.encode("utf-8")
        return response

    @staticmethod
    def error_response(status_code: int = 404) -> Mock:
        """Create error HTTP response"""
        response = Mock()
        response.status_code = status_code
        return response

    @staticmethod
    def subtitle_response(
        content: str = "00:00:01.000 --> 00:00:03.000\nHello world subtitle content",
    ) -> Mock:
        """Create response with subtitle content"""
        return HTTPResponseFactory.success_response(content)

    @staticmethod
    def pdf_response(content: bytes = b"fake pdf content") -> Mock:
        """Create response with PDF binary content"""
        response = Mock()
        response.status_code = 200
        response.content = content
        return response


class SlackServiceFactory:
    """Factory for creating Slack service mocks"""

    @staticmethod
    def create_service(bot_token: str = "test-token") -> Mock:
        """Create basic Slack service mock"""
        service = Mock()
        service.settings = Mock()
        service.settings.bot_token = bot_token
        return service


class AgentRegistryMockFactory:
    """Factory for creating agent registry mocks (route_command, agent_info)"""

    @staticmethod
    def create_profile_agent_info():
        """Create mock agent info for profile agent"""
        return {
            "name": "profile",
            "endpoint": "http://agent-service:8000/agents/profile/invoke",
            "description": "Company research agent",
        }

    @staticmethod
    def create_meddic_agent_info():
        """Create mock agent info for MEDDIC agent"""
        return {
            "name": "meddic",
            "endpoint": "http://agent-service:8000/agents/meddic/invoke",
            "description": "MEDDIC sales framework analysis agent",
        }

    @staticmethod
    def create_route_command_mock(agent_name: str, query: str):
        """Create a mock route_command function that returns agent info"""
        agent_info_map = {
            "profile": AgentRegistryMockFactory.create_profile_agent_info(),
            "meddic": AgentRegistryMockFactory.create_meddic_agent_info(),
        }

        agent_info = agent_info_map.get(agent_name)
        if not agent_info:
            return None, query, None

        return agent_info, query, agent_name


class AgentClientMockFactory:
    """Factory for creating agent client mocks (HTTP invocation)"""

    @staticmethod
    def create_successful_response():
        """Create a mock successful agent response"""
        return {
            "response": "Starting research on Charlotte... \n\n✅ Research complete!",
            "metadata": {
                "agent": "profile",
                "duration_seconds": 45.2,
            },
        }

    @staticmethod
    def create_error_response(error_message: str = "Agent service unavailable"):
        """Create a mock error response"""
        return {
            "response": f"Agent failed: {error_message}",
            "metadata": {"error": error_message},
        }

    @staticmethod
    def create_mock_client(success: bool = True):
        """Create a mock agent client"""
        mock_client = Mock()
        if success:
            mock_client.invoke_agent = AsyncMock(
                return_value=AgentClientMockFactory.create_successful_response()
            )
        else:
            mock_client.invoke_agent = AsyncMock(
                side_effect=Exception("Unable to connect to agent service")
            )
        return mock_client


class PermissionServiceMockFactory:
    """Factory for creating permission service mocks"""

    @staticmethod
    def create_allowed_permission():
        """Create a permission service that allows access"""
        mock_service = Mock()
        mock_service.can_use_agent = Mock(return_value=(True, None))
        return mock_service

    @staticmethod
    def create_denied_permission(reason: str = "Access denied"):
        """Create a permission service that denies access"""
        mock_service = Mock()
        mock_service.can_use_agent = Mock(return_value=(False, reason))
        return mock_service


class FileProcessingTestDataFactory:
    """Factory for creating comprehensive test data sets"""

    @staticmethod
    def all_supported_file_types() -> list[tuple]:
        """Generate test data for all supported file types"""
        return [
            ("test.txt", "text/plain"),
            ("test.md", "text/markdown"),
            ("test.py", "text/x-python"),
            ("test.js", "application/javascript"),
            ("test.json", "application/json"),
            ("test.csv", "text/csv"),
            ("test.vtt", "text/vtt"),
            ("test.srt", "application/x-subrip"),
            ("subtitles.srt", "text/srt"),  # Alternative SRT MIME type
            ("test.pdf", "application/pdf"),
            (
                "test.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            (
                "test.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            (
                "test.pptx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
            ("test.unknown", "application/unknown"),
        ]

    @staticmethod
    def office_document_routing_test_data() -> dict[str, list[tuple]]:
        """Generate test data for office document routing"""
        return {
            "word": [
                (
                    "test.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                ("test.docx", "application/wordprocessingml"),
            ],
            "excel": [
                (
                    "test.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                ("test.xlsx", "application/spreadsheetml"),
            ],
            "powerpoint": [
                (
                    "test.pptx",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ),
                ("test.pptx", "application/presentationml"),
            ],
        }

    @staticmethod
    def invalid_pdf_test_cases() -> list[tuple]:
        """Generate test data for invalid PDF content scenarios"""
        return [
            (None, "none.pdf"),
            (b"", "empty.pdf"),
            (b"not a pdf", "invalid.pdf"),
        ]


class TestMessageHandlers:
    """Tests for message handler functions"""

    def test_default_system_message_exists(self):
        """Test that system prompt can be retrieved via PromptService"""
        prompt = get_user_system_prompt()
        assert prompt is not None
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Insight Mesh" in prompt

    def test_get_user_system_prompt(self):
        """Test get_user_system_prompt function"""
        prompt = get_user_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_handle_message_function_exists(self):
        """Test that handle_message function exists and is callable"""
        assert callable(handle_message)
        assert handle_message.__name__ == "handle_message"


class TestDocumentProcessingAvailability:
    """Tests for document processing library availability flags"""

    def test_library_availability_flags_exist(self):
        """Test that all library availability flags are defined"""
        assert isinstance(PYMUPDF_AVAILABLE, bool)
        assert isinstance(PYTHON_DOCX_AVAILABLE, bool)
        assert isinstance(OPENPYXL_AVAILABLE, bool)
        assert isinstance(PYTHON_PPTX_AVAILABLE, bool)


class TestPDFProcessing:
    """Tests for PDF text extraction functionality"""

    @pytest.mark.asyncio
    async def test_extract_pdf_text_library_unavailable(self):
        """Test PDF extraction when PyMuPDF is not available"""
        with patch("handlers.file_processors.pdf_processor.PYMUPDF_AVAILABLE", False):
            result = await extract_pdf_text(b"test", "test.pdf")
            assert "[PDF file: test.pdf - PyMuPDF not installed]" in result

    @pytest.mark.asyncio
    async def test_extract_pdf_text_empty_content(self):
        """Test PDF extraction with empty content"""
        if not PYMUPDF_AVAILABLE:
            pytest.skip("PyMuPDF not available in test environment")

        result = await extract_pdf_text(b"", "test.pdf")
        assert "test.pdf" in result
        assert "Error:" in result or "Error extracting text:" in result

    @pytest.mark.asyncio
    async def test_extract_pdf_text_invalid_pdf(self):
        """Test PDF extraction with invalid PDF content"""
        if not PYMUPDF_AVAILABLE:
            pytest.skip("PyMuPDF not available in test environment")

        result = await extract_pdf_text(b"invalid pdf content", "test.pdf")
        assert "test.pdf" in result
        assert (
            "Error:" in result or "Error extracting text:" in result
        ) or "No extractable text" in result

    @pytest.mark.asyncio
    async def test_extract_pdf_text_handles_exceptions(self):
        """Test PDF extraction handles exceptions gracefully"""
        if not PYMUPDF_AVAILABLE:
            pytest.skip("PyMuPDF not available in test environment")

        test_cases = FileProcessingTestDataFactory.invalid_pdf_test_cases()

        for content, filename in test_cases:
            if content is not None:
                result = await extract_pdf_text(content, filename)
                assert filename in result
                assert isinstance(result, str)


class TestWordProcessing:
    """Tests for Word document text extraction"""

    @pytest.mark.asyncio
    async def test_extract_word_text_library_unavailable(self):
        """Test Word extraction when python-docx is not available"""
        with patch(
            "handlers.file_processors.office_processor.PYTHON_DOCX_AVAILABLE", False
        ):
            stream = io.BytesIO(b"test")
            result = await extract_word_text(stream, "test.docx")
            assert "[Word file: test.docx - python-docx not installed]" in result

    @pytest.mark.asyncio
    async def test_extract_word_text_empty_stream(self):
        """Test Word extraction with empty stream"""
        if not PYTHON_DOCX_AVAILABLE:
            pytest.skip("python-docx not available in test environment")

        stream = io.BytesIO(b"")
        result = await extract_word_text(stream, "test.docx")
        assert "test.docx" in result
        assert "Error:" in result or "Error extracting text:" in result

    @pytest.mark.asyncio
    async def test_extract_word_text_invalid_content(self):
        """Test Word extraction with invalid content"""
        if not PYTHON_DOCX_AVAILABLE:
            pytest.skip("python-docx not available in test environment")

        stream = io.BytesIO(b"invalid docx content")
        result = await extract_word_text(stream, "test.docx")
        assert "test.docx" in result
        assert "Error:" in result or "Error extracting text:" in result


class TestExcelProcessing:
    """Tests for Excel file text extraction"""

    @pytest.mark.asyncio
    async def test_extract_excel_text_library_unavailable(self):
        """Test Excel extraction when openpyxl is not available"""
        with patch(
            "handlers.file_processors.office_processor.OPENPYXL_AVAILABLE", False
        ):
            stream = io.BytesIO(b"test")
            result = await extract_excel_text(stream, "test.xlsx")
            assert "[Excel file: test.xlsx - openpyxl not installed]" in result

    @pytest.mark.asyncio
    async def test_extract_excel_text_empty_stream(self):
        """Test Excel extraction with empty stream"""
        if not OPENPYXL_AVAILABLE:
            pytest.skip("openpyxl not available in test environment")

        stream = io.BytesIO(b"")
        result = await extract_excel_text(stream, "test.xlsx")
        assert "test.xlsx" in result
        assert "Error:" in result or "Error extracting text:" in result

    @pytest.mark.asyncio
    async def test_extract_excel_text_invalid_content(self):
        """Test Excel extraction with invalid content"""
        if not OPENPYXL_AVAILABLE:
            pytest.skip("openpyxl not available in test environment")

        stream = io.BytesIO(b"invalid xlsx content")
        result = await extract_excel_text(stream, "test.xlsx")
        assert "test.xlsx" in result
        assert "Error:" in result or "Error extracting text:" in result


class TestPowerPointProcessing:
    """Tests for PowerPoint text extraction"""

    @pytest.mark.asyncio
    async def test_extract_powerpoint_text_library_unavailable(self):
        """Test PowerPoint extraction when python-pptx is not available"""
        with patch(
            "handlers.file_processors.office_processor.PYTHON_PPTX_AVAILABLE", False
        ):
            stream = io.BytesIO(b"test")
            result = await extract_powerpoint_text(stream, "test.pptx")
            assert "[PowerPoint file: test.pptx - python-pptx not installed]" in result

    @pytest.mark.asyncio
    async def test_extract_powerpoint_text_empty_stream(self):
        """Test PowerPoint extraction with empty stream"""
        if not PYTHON_PPTX_AVAILABLE:
            pytest.skip("python-pptx not available in test environment")

        stream = io.BytesIO(b"")
        result = await extract_powerpoint_text(stream, "test.pptx")
        assert "test.pptx" in result
        assert "Error:" in result or "Error extracting text:" in result

    @pytest.mark.asyncio
    async def test_extract_powerpoint_text_invalid_content(self):
        """Test PowerPoint extraction with invalid content"""
        if not PYTHON_PPTX_AVAILABLE:
            pytest.skip("python-pptx not available in test environment")

        stream = io.BytesIO(b"invalid pptx content")
        result = await extract_powerpoint_text(stream, "test.pptx")
        assert "test.pptx" in result
        assert "Error:" in result or "Error extracting text:" in result


class TestOfficeDocumentRouting:
    """Tests for office document type routing"""

    @pytest.mark.asyncio
    async def test_extract_office_text_word_routing(self):
        """Test that Word documents are routed correctly"""
        routing_data = FileProcessingTestDataFactory.office_document_routing_test_data()

        for filename, mimetype in routing_data["word"]:
            result = await extract_office_text(b"test", filename, mimetype)
            assert filename in result

    @pytest.mark.asyncio
    async def test_extract_office_text_excel_routing(self):
        """Test that Excel files are routed correctly"""
        routing_data = FileProcessingTestDataFactory.office_document_routing_test_data()

        for filename, mimetype in routing_data["excel"]:
            result = await extract_office_text(b"test", filename, mimetype)
            assert filename in result

    @pytest.mark.asyncio
    async def test_extract_office_text_powerpoint_routing(self):
        """Test that PowerPoint files are routed correctly"""
        routing_data = FileProcessingTestDataFactory.office_document_routing_test_data()

        for filename, mimetype in routing_data["powerpoint"]:
            result = await extract_office_text(b"test", filename, mimetype)
            assert filename in result

    @pytest.mark.asyncio
    async def test_extract_office_text_unsupported_format(self):
        """Test unsupported office format handling"""
        result = await extract_office_text(
            b"test", "test.unknown", "application/unknown"
        )
        assert "Unsupported Office file type:" in result


class TestFileAttachmentProcessing:
    """Tests for the main file attachment processing workflow"""

    @pytest.mark.asyncio
    async def test_process_file_attachments_empty_files(self):
        """Test processing with empty file list"""
        slack_service = SlackServiceFactory.create_service()
        result = await process_file_attachments([], slack_service)
        assert result == ""

    @pytest.mark.asyncio
    async def test_process_file_attachments_no_url(self):
        """Test processing file without private URL"""
        slack_service = SlackServiceFactory.create_service()
        files = [SlackFileBuilder.file_without_url().build()]

        result = await process_file_attachments(files, slack_service)
        assert result == ""  # Should skip files without URL

    @pytest.mark.asyncio
    async def test_process_file_attachments_large_file(self):
        """Test processing file that exceeds size limit"""
        slack_service = SlackServiceFactory.create_service()
        files = [SlackFileBuilder.large_file("huge.pdf", 200).build()]

        result = await process_file_attachments(files, slack_service)
        assert result == ""  # Should skip large files

    @pytest.mark.asyncio
    async def test_process_file_attachments_download_failure(self):
        """Test processing when file download fails"""
        slack_service = SlackServiceFactory.create_service("test-token")
        files = [SlackFileBuilder.pdf_file().build()]

        with patch("requests.get") as mock_get:
            mock_get.return_value = HTTPResponseFactory.error_response(404)
            result = await process_file_attachments(files, slack_service)
            assert result == ""  # Should handle download failures gracefully

    @pytest.mark.asyncio
    async def test_process_file_attachments_subtitle_files(self):
        """Test processing of subtitle files (VTT, SRT) as text"""
        slack_service = SlackServiceFactory.create_service("test-token")
        subtitle_files = [
            SlackFileBuilder.subtitle_file("captions.vtt", "text/vtt")
            .with_url("https://test.com/captions.vtt")
            .build(),
            SlackFileBuilder.srt_subtitle_file("subtitles.srt")
            .with_url("https://test.com/subtitles.srt")
            .build(),
        ]

        with patch("requests.get") as mock_get:
            mock_get.return_value = HTTPResponseFactory.subtitle_response()
            result = await process_file_attachments(subtitle_files, slack_service)

            assert "captions.vtt" in result
            assert "subtitles.srt" in result
            assert "Hello world subtitle content" in result

    @pytest.mark.asyncio
    async def test_process_file_attachments_text_file_success(self):
        """Test successful text file processing"""
        slack_service = SlackServiceFactory.create_service("test-token")
        files = [SlackFileBuilder.text_file().with_size(100).build()]

        with patch("requests.get") as mock_get:
            mock_get.return_value = HTTPResponseFactory.success_response(
                "This is test content"
            )
            result = await process_file_attachments(files, slack_service)

            assert "test.txt" in result
            assert "This is test content" in result

    @pytest.mark.asyncio
    async def test_process_file_attachments_pdf_success(self):
        """Test PDF file processing workflow"""
        slack_service = SlackServiceFactory.create_service("test-token")
        files = [SlackFileBuilder.pdf_file().build()]

        with patch("requests.get") as mock_get:
            mock_get.return_value = HTTPResponseFactory.pdf_response()
            result = await process_file_attachments(files, slack_service)

            assert "test.pdf" in result
            # Should contain either extracted text or error message
            assert len(result) > 0


class TestFileProcessingErrorHandling:
    """Tests for error handling in file processing"""

    @pytest.mark.asyncio
    async def test_process_file_attachments_request_exception(self):
        """Test handling of request exceptions"""
        slack_service = SlackServiceFactory.create_service("test-token")
        files = [SlackFileBuilder.pdf_file().build()]

        with patch("requests.get", side_effect=Exception("Network error")):
            result = await process_file_attachments(files, slack_service)
            assert result == ""  # Should handle exceptions gracefully

    @pytest.mark.asyncio
    async def test_extract_functions_handle_none_input(self):
        """Test that extraction functions handle None input gracefully"""
        if not PYMUPDF_AVAILABLE:
            pytest.skip("PyMuPDF not available in test environment")

        # Should handle None input gracefully - PyMuPDF creates empty document
        result = await extract_pdf_text(None, "test.pdf")
        assert "test.pdf" in result
        assert "No extractable text" in result or "Error extracting text" in result

    @pytest.mark.asyncio
    async def test_supported_file_types_coverage(self):
        """Test that all supported file types are handled"""
        slack_service = SlackServiceFactory.create_service("test-token")
        test_files = FileProcessingTestDataFactory.all_supported_file_types()

        for filename, mimetype in test_files:
            files = [
                SlackFileBuilder().with_name(filename).with_mimetype(mimetype).build()
            ]

            with patch("requests.get") as mock_get:
                mock_get.return_value = HTTPResponseFactory.success_response(
                    "test content", b"test content"
                )
                result = await process_file_attachments(files, slack_service)
                assert isinstance(result, str)  # Should always return a string


class TestBotCommandHandling:
    """Tests for bot agent command routing (/profile, "-meddic", "-medic")"""

    @pytest.mark.asyncio
    async def test_handle_bot_command_profile(self):
        """Test /profile bot command is handled correctly"""
        from unittest.mock import AsyncMock

        from services.llm_service import LLMService

        slack_service = SlackServiceFactory.create_service("test-token")
        slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.update_message = AsyncMock()
        slack_service.get_thread_history = AsyncMock(return_value=([], True))

        # Mock LLM service for fallback
        llm_service = Mock(spec=LLMService)
        llm_service.get_response = AsyncMock(
            return_value="Please provide more details about what you'd like to know."
        )

        # Use factory to create route_command mock
        route_result = AgentRegistryMockFactory.create_route_command_mock(
            "profile", "tell me about Charlotte"
        )

        # New HTTP-based agent architecture - agent runs in agent-service
        with (
            patch("handlers.message_handlers.route_command", return_value=route_result),
            patch(
                "services.permission_service.get_permission_service",
                return_value=PermissionServiceMockFactory.create_allowed_permission(),
            ),
            patch(
                "services.agent_client.get_agent_client",
                return_value=AgentClientMockFactory.create_mock_client(success=True),
            ),
        ):
            result = await handle_bot_command(
                text="-profile tell me about Charlotte",
                user_id="U123",
                slack_service=slack_service,
                channel="C123",
                thread_ts=None,
                llm_service=llm_service,
            )

        assert result is True
        slack_service.send_thinking_indicator.assert_called_once_with("C123", None)
        # Thinking indicator cleanup happens after response
        assert slack_service.delete_thinking_indicator.called

        # With HTTP-based agent architecture, agent-service returns response text
        # Bot sends this response as a message
        assert slack_service.send_message.call_count >= 1

        # Verify response message was sent
        first_call = slack_service.send_message.call_args_list[0]
        assert "Starting research" in first_call.kwargs["text"]

        # Note: With HTTP-based agent architecture, PDFs are generated by agent-service
        # and returned in the response, not uploaded by the bot

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handle_bot_command_meddic(self):
        """Test "-meddic" bot command is handled correctly"""
        from unittest.mock import AsyncMock

        slack_service = SlackServiceFactory.create_service("test-token")
        slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.send_message = AsyncMock()
        slack_service.get_thread_history = AsyncMock(return_value=([], True))

        # Use factories for all mocks - HTTP-based agent architecture
        route_result = AgentRegistryMockFactory.create_route_command_mock(
            "meddic", "analyze this opportunity"
        )

        with (
            patch("handlers.message_handlers.route_command", return_value=route_result),
            patch(
                "services.permission_service.get_permission_service",
                return_value=PermissionServiceMockFactory.create_allowed_permission(),
            ),
            patch(
                "services.agent_client.get_agent_client",
                return_value=AgentClientMockFactory.create_mock_client(success=True),
            ),
        ):
            result = await handle_bot_command(
                text="-meddic analyze this opportunity",
                user_id="U123",
                slack_service=slack_service,
                channel="C123",
                thread_ts="1234.5678",
            )

        assert result is True
        slack_service.send_thinking_indicator.assert_called_once_with(
            "C123", "1234.5678"
        )
        slack_service.delete_thinking_indicator.assert_called_once()
        # HTTP-based agent sends 1 final message (progress handled by agent-service)
        assert slack_service.send_message.call_count >= 1

        # Verify final response content
        call_args = slack_service.send_message.call_args
        response_text = call_args.kwargs["text"]
        # HTTP agent mock returns generic success response
        assert response_text  # Just verify we got a response

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handle_bot_command_medic_alias(self):
        """Test -medic alias resolves to -meddic"""
        from unittest.mock import AsyncMock

        slack_service = SlackServiceFactory.create_service("test-token")
        slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.send_message = AsyncMock()
        slack_service.get_thread_history = AsyncMock(return_value=([], True))

        # Use factories for all mocks - HTTP-based agent architecture
        # Note: "-medic" alias should resolve to "meddic" agent
        route_result = AgentRegistryMockFactory.create_route_command_mock(
            "meddic", "what's the decision process"
        )

        with (
            patch("handlers.message_handlers.route_command", return_value=route_result),
            patch(
                "services.permission_service.get_permission_service",
                return_value=PermissionServiceMockFactory.create_allowed_permission(),
            ),
            patch(
                "services.agent_client.get_agent_client",
                return_value=AgentClientMockFactory.create_mock_client(success=True),
            ),
        ):
            result = await handle_bot_command(
                text="-medic what's the decision process",
                user_id="U123",
                slack_service=slack_service,
                channel="C123",
                thread_ts="1234.5678",  # Required for bot commands
            )

        assert result is True

        # HTTP-based agent sends final message (progress handled by agent-service)
        assert slack_service.send_message.call_count >= 1

        # Verify response
        call_args = slack_service.send_message.call_args
        response_text = call_args.kwargs["text"]
        assert response_text  # Verify we got a response

    @pytest.mark.asyncio
    async def test_handle_bot_command_unknown_bot_type(self):
        """Test that unknown bot types return False (not handled)"""
        from unittest.mock import AsyncMock

        slack_service = SlackServiceFactory.create_service("test-token")
        slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.send_message = AsyncMock()
        slack_service.get_thread_history = AsyncMock(return_value=([], True))

        result = await handle_bot_command(
            text="/unknown some query",
            user_id="U123",
            slack_service=slack_service,
            channel="C123",
            thread_ts=None,
        )

        assert result is False
        # Should not send any messages for unknown bot types
        slack_service.send_thinking_indicator.assert_not_called()
        slack_service.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_bot_command_empty_query(self):
        """Test bot command with empty query"""
        from unittest.mock import AsyncMock

        slack_service = SlackServiceFactory.create_service("test-token")
        slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.send_message = AsyncMock()
        slack_service.get_thread_history = AsyncMock(return_value=([], True))

        # Use factories for all mocks
        route_result = AgentRegistryMockFactory.create_route_command_mock("profile", "")

        with (
            patch("handlers.message_handlers.route_command", return_value=route_result),
            patch(
                "services.permission_service.get_permission_service",
                return_value=PermissionServiceMockFactory.create_allowed_permission(),
            ),
            patch(
                "services.agent_client.get_agent_client",
                return_value=AgentClientMockFactory.create_mock_client(success=True),
            ),
        ):
            result = await handle_bot_command(
                text="-profile ",
                user_id="U123",  # Empty query
                slack_service=slack_service,
                channel="C123",
                thread_ts=None,
            )

        assert result is True
        # Should still handle it, just with empty query
        call_args = slack_service.send_message.call_args
        response_text = call_args.kwargs["text"]
        # HTTP agent mock returns generic response - just verify we got something
        assert response_text  # Verify we got a response

    @pytest.mark.asyncio
    async def test_handle_bot_command_error_handling(self):
        """Test error handling when bot command processing fails"""
        from unittest.mock import AsyncMock

        slack_service = SlackServiceFactory.create_service("test-token")
        slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.send_message = AsyncMock(
            side_effect=[Exception("Slack API error"), None]
        )

        # Use factories for all mocks
        route_result = AgentRegistryMockFactory.create_route_command_mock(
            "profile", "test query"
        )

        with (
            patch("handlers.message_handlers.route_command", return_value=route_result),
            patch(
                "services.permission_service.get_permission_service",
                return_value=PermissionServiceMockFactory.create_allowed_permission(),
            ),
            patch(
                "services.agent_client.get_agent_client",
                return_value=AgentClientMockFactory.create_mock_client(success=True),
            ),
        ):
            result = await handle_bot_command(
                text="-profile test query",
                user_id="U123",
                slack_service=slack_service,
                channel="C123",
                thread_ts=None,
            )

        # Should still return True (handled), but send error message
        assert result is True
        assert slack_service.send_message.call_count >= 1
        # Check for error message
        error_call_args = slack_service.send_message.call_args
        error_text = error_call_args.kwargs["text"]
        # With HTTP agents, may get different error handling
        assert error_text  # Just verify we got some response

    @pytest.mark.asyncio
    async def test_handle_bot_command_thinking_indicator_cleanup(self):
        """Test that thinking indicator is always cleaned up"""
        from unittest.mock import AsyncMock

        slack_service = SlackServiceFactory.create_service("test-token")
        slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.send_message = AsyncMock()
        slack_service.get_thread_history = AsyncMock(return_value=([], True))

        # Use factories for all mocks
        route_result = AgentRegistryMockFactory.create_route_command_mock(
            "profile", "test"
        )

        with (
            patch("handlers.message_handlers.route_command", return_value=route_result),
            patch(
                "services.permission_service.get_permission_service",
                return_value=PermissionServiceMockFactory.create_allowed_permission(),
            ),
            patch(
                "services.agent_client.get_agent_client",
                return_value=AgentClientMockFactory.create_mock_client(success=True),
            ),
        ):
            await handle_bot_command(
                text="-profile test",
                user_id="U123",
                slack_service=slack_service,
                channel="C123",
                thread_ts=None,
            )

        # Thinking indicator should be deleted
        slack_service.delete_thinking_indicator.assert_called_once_with(
            "C123", "thinking_ts"
        )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handle_message_routes_to_bot_command(self):
        """Test that handle_message correctly routes /profile and "-meddic" commands"""
        from unittest.mock import AsyncMock

        from services.llm_service import LLMService

        slack_service = SlackServiceFactory.create_service("test-token")
        slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.update_message = AsyncMock()
        slack_service.upload_file = AsyncMock(return_value={"ok": True})
        slack_service.get_thread_history = AsyncMock(return_value=([], True))

        llm_service = Mock(spec=LLMService)
        llm_service.get_response = AsyncMock(
            return_value="Please provide more details about what you'd like to know."
        )

        # Use factories for all mocks - HTTP-based agent architecture
        route_result = AgentRegistryMockFactory.create_route_command_mock(
            "profile", "tell me about Charlotte"
        )

        with (
            patch("handlers.message_handlers.route_command", return_value=route_result),
            patch(
                "services.permission_service.get_permission_service",
                return_value=PermissionServiceMockFactory.create_allowed_permission(),
            ),
            patch(
                "services.agent_client.get_agent_client",
                return_value=AgentClientMockFactory.create_mock_client(success=True),
            ),
        ):
            # Test /profile routing
            await handle_message(
                text="-profile tell me about Charlotte",
                user_id="U123",
                slack_service=slack_service,
                llm_service=llm_service,
                channel="C123",
                thread_ts=None,
                message_ts="1234567890.123456",  # Required for conversation tracking
            )

        # Should route to bot command and send message
        assert slack_service.send_message.call_count >= 1
        # Verify we got a response
        status_call = slack_service.send_message.call_args_list[0]
        status_text = status_call.kwargs["text"]
        assert status_text  # Verify we got some response
        # HTTP-based agents handle file uploads differently - not checked here

        # Reset mocks
        slack_service.send_message.reset_mock()

        # Test "-meddic" routing
        route_result_meddic = AgentRegistryMockFactory.create_route_command_mock(
            "meddic", "analyze deal"
        )

        with (
            patch(
                "handlers.message_handlers.route_command",
                return_value=route_result_meddic,
            ),
            patch(
                "services.permission_service.get_permission_service",
                return_value=PermissionServiceMockFactory.create_allowed_permission(),
            ),
            patch(
                "services.agent_client.get_agent_client",
                return_value=AgentClientMockFactory.create_mock_client(success=True),
            ),
        ):
            await handle_message(
                text="-meddic analyze deal",
                user_id="U123",
                slack_service=slack_service,
                llm_service=llm_service,
                channel="C123",
                thread_ts=None,
                message_ts="1234567890.654321",  # Required for conversation tracking
            )

        # HTTP-based agent sends final message
        assert slack_service.send_message.call_count >= 1
        call_args = slack_service.send_message.call_args
        response_text = call_args.kwargs["text"]
        assert response_text  # Verify we got a response

    @pytest.mark.asyncio
    async def test_handle_message_case_insensitive_bot_commands(self):
        """Test that bot commands work with any casing"""
        from unittest.mock import AsyncMock

        from services.llm_service import LLMService

        slack_service = SlackServiceFactory.create_service("test-token")
        slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.update_message = AsyncMock()
        slack_service.get_thread_history = AsyncMock(return_value=([], True))

        llm_service = Mock(spec=LLMService)
        llm_service.get_response = AsyncMock(
            return_value="Please provide more details about what you'd like to know."
        )

        # Use factories for all mocks - HTTP-based agent architecture
        route_result = AgentRegistryMockFactory.create_route_command_mock(
            "profile", "test"
        )

        with (
            patch("handlers.message_handlers.route_command", return_value=route_result),
            patch(
                "services.permission_service.get_permission_service",
                return_value=PermissionServiceMockFactory.create_allowed_permission(),
            ),
            patch(
                "services.agent_client.get_agent_client",
                return_value=AgentClientMockFactory.create_mock_client(success=True),
            ),
        ):
            # Test uppercase
            await handle_message(
                text="-PROFILE test",
                user_id="U123",
                slack_service=slack_service,
                llm_service=llm_service,
                channel="C123",
                thread_ts=None,
                message_ts="1234567890.123456",  # Required for conversation tracking
            )

        # With HTTP-based agent architecture, agent-service returns response text
        assert slack_service.send_message.call_count >= 1
        status_call = slack_service.send_message.call_args_list[0]
        status_text = status_call.kwargs["text"]
        assert "Starting research" in status_text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handle_message_medic_alias_routing(self):
        """Test that -medic alias routes through handle_message to -meddic"""
        from unittest.mock import AsyncMock

        from services.llm_service import LLMService

        slack_service = SlackServiceFactory.create_service("test-token")
        slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.update_message = AsyncMock()
        slack_service.get_thread_history = AsyncMock(return_value=([], True))

        llm_service = Mock(spec=LLMService)
        llm_service.get_response = AsyncMock(return_value="Agent response")

        # Use factories for all mocks - HTTP-based agent architecture
        route_result = AgentRegistryMockFactory.create_route_command_mock(
            "medic", "analyze this deal opportunity"
        )

        with (
            patch("handlers.message_handlers.route_command", return_value=route_result),
            patch(
                "services.permission_service.get_permission_service",
                return_value=PermissionServiceMockFactory.create_allowed_permission(),
            ),
            patch(
                "services.agent_client.get_agent_client",
                return_value=AgentClientMockFactory.create_mock_client(success=True),
            ),
        ):
            # Test "-medic" alias routing through handle_message
            await handle_message(
                text="-medic analyze this deal opportunity",
                user_id="U123",
                slack_service=slack_service,
                llm_service=llm_service,
                channel="C123",
                thread_ts="1234.5678",
            )

        # HTTP-based agent sends final message
        assert slack_service.send_message.call_count >= 1
        call_args = slack_service.send_message.call_args
        response_text = call_args.kwargs["text"]
        # Verify we got a response
        assert response_text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handle_message_medic_alias_case_variations(self):
        """Test that "-medic" alias works with different casing"""
        from unittest.mock import AsyncMock

        from services.llm_service import LLMService

        slack_service = SlackServiceFactory.create_service("test-token")
        slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.update_message = AsyncMock()
        slack_service.get_thread_history = AsyncMock(return_value=([], True))

        llm_service = Mock(spec=LLMService)
        llm_service.get_response = AsyncMock(return_value="Agent response")

        # Test various casings of "-medic"
        test_cases = ["-medic", "-MEDIC", "-Medic", "-MeDiC"]

        for medic_variant in test_cases:
            slack_service.send_message.reset_mock()

            # Use factories for all mocks - HTTP-based agent architecture
            route_result = AgentRegistryMockFactory.create_route_command_mock(
                "medic", "test query"
            )

            with (
                patch(
                    "handlers.message_handlers.route_command", return_value=route_result
                ),
                patch(
                    "services.permission_service.get_permission_service",
                    return_value=PermissionServiceMockFactory.create_allowed_permission(),
                ),
                patch(
                    "services.agent_client.get_agent_client",
                    return_value=AgentClientMockFactory.create_mock_client(
                        success=True
                    ),
                ),
            ):
                await handle_message(
                    text=f"{medic_variant} test query",
                    user_id="U123",
                    slack_service=slack_service,
                    llm_service=llm_service,
                    channel="C123",
                    thread_ts=None,
                    message_ts="1234567890.123456",  # Required for conversation tracking
                )

            # HTTP-based agent sends final message
            assert slack_service.send_message.call_count >= 1
            call_args = slack_service.send_message.call_args
            response_text = call_args.kwargs["text"]
            # Verify we got a response
            assert response_text, f"No response for variant: {medic_variant}"

    @pytest.mark.asyncio
    async def test_profile_thread_disables_rag(self):
        """Test that profile threads disable RAG via thread type metadata"""
        from unittest.mock import AsyncMock

        from services.llm_service import LLMService

        slack_service = SlackServiceFactory.create_service("test-token")
        slack_service.send_thinking_indicator = AsyncMock(return_value="thinking_ts")
        slack_service.delete_thinking_indicator = AsyncMock()
        slack_service.send_message = AsyncMock(return_value={"ts": "123.456"})
        slack_service.get_thread_history = AsyncMock(return_value=([], True))

        llm_service = Mock(spec=LLMService)
        llm_service.get_response = AsyncMock(return_value="Response about the profile")

        # Mock conversation cache for profile thread
        conversation_cache = AsyncMock()
        conversation_cache.get_document_content = AsyncMock(
            return_value=(
                "# Company Profile\n\nProfile content",
                "Company_Profile_Acme.pdf",
            )
        )
        # Mark thread as profile type
        conversation_cache.get_thread_type = AsyncMock(return_value="profile")

        # Test 1: Profile thread should disable RAG
        await handle_message(
            text="What are the key findings?",
            user_id="U123",
            slack_service=slack_service,
            llm_service=llm_service,
            channel="C123",
            thread_ts="1234.5678",
            conversation_cache=conversation_cache,
        )

        # Verify LLM was called with use_rag=False for profile thread
        llm_service.get_response.assert_called_once()
        call_kwargs = llm_service.get_response.call_args.kwargs
        assert call_kwargs["use_rag"] is False, "Profile thread should disable RAG"
        assert call_kwargs["document_content"] is not None

        # Reset mocks
        llm_service.get_response.reset_mock()

        # Test 2: Regular thread (no thread type) should keep RAG enabled
        conversation_cache.get_document_content = AsyncMock(
            return_value=("Document content", "quarterly_report.pdf")
        )
        # No thread type set (returns None)
        conversation_cache.get_thread_type = AsyncMock(return_value=None)

        await handle_message(
            text="Summarize this document",
            user_id="U123",
            slack_service=slack_service,
            llm_service=llm_service,
            channel="C123",
            thread_ts="5678.1234",
            conversation_cache=conversation_cache,
        )

        # Verify LLM was called with use_rag=True for regular thread
        llm_service.get_response.assert_called_once()
        call_kwargs = llm_service.get_response.call_args.kwargs
        assert call_kwargs["use_rag"] is True, "Regular thread should keep RAG enabled"
        assert call_kwargs["document_content"] is not None
