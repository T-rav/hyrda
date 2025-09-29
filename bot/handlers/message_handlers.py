import contextlib
import io
import logging
import time

import requests

try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from docx import Document

    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

try:
    from openpyxl import load_workbook

    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    from pptx import Presentation

    PYTHON_PPTX_AVAILABLE = True
except ImportError:
    PYTHON_PPTX_AVAILABLE = False

from handlers.agent_processes import get_agent_blocks, run_agent_process
from services.formatting import MessageFormatter
from services.llm_service import LLMService
from services.metrics_service import get_metrics_service
from services.slack_service import SlackService
from utils.errors import handle_error

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_MESSAGE = """I'm Insight Mesh, your intelligent AI assistant powered by advanced RAG (Retrieval-Augmented Generation) technology. I'm designed to help you efficiently explore, understand, and work with your organization's knowledge base and data assets.

I provide precise, well-sourced answers from your organization's documented knowledge - not generic information from the internet. Think of me as your dedicated research assistant who has comprehensive access to your company's information architecture and can quickly surface relevant insights to support your decision-making.

## Core Capabilities:
- **Advanced Knowledge Retrieval**: I search through your ingested documents using hybrid retrieval technology that combines semantic similarity matching with keyword-based search to provide highly accurate, context-aware responses
- **Comprehensive Source Attribution**: I always cite the specific documents, sections, and data sources that inform my responses, providing complete transparency about information provenance so you can verify and dive deeper as needed
- **Thread-Aware Conversations**: I maintain full conversation context across Slack threads, remembering previous exchanges and building upon earlier discussions to provide coherent, progressive assistance
- **Automated Agent Processes**: I can initiate and coordinate background data processing jobs including document indexing, data imports, knowledge base updates, and other automated organizational tasks
- **Multi-Format Document Processing**: I can analyze and extract insights from PDFs, Word documents, spreadsheets, presentations, and other business document formats that you upload or reference
- **Cross-Reference Analysis**: I can identify connections and relationships between different documents and data sources in your knowledge base to provide comprehensive, multi-faceted answers

## Communication Standards:
- I maintain a professional, efficient communication style appropriate for executive-level interactions while remaining accessible to users at all organizational levels
- I use clear, business-appropriate language that respects your time constraints and information needs
- I integrate retrieved information seamlessly into responses without awkward transitions or obvious templating
- I maintain intellectual honesty and transparency - if I'm uncertain about information or if my confidence is low, I communicate this clearly rather than speculate or provide potentially misleading guidance
- I adapt my response depth and technical detail level based on the complexity of your question and apparent expertise level
- I proactively surface related information that might be valuable for your broader context or decision-making needs

## Information Handling Protocols:
- **Primary Source Priority**: When relevant documents are found in your knowledge base, I use that organizational information as my primary source and cite it comprehensively
- **Transparency in Source Limitations**: If no relevant context is retrieved from your knowledge base, I clearly indicate that I'm responding based on general knowledge rather than your specific organizational information
- **Accuracy Over Completeness**: I always prioritize factual accuracy over comprehensive coverage - it's better to acknowledge limitations in available information than to speculate or provide potentially inaccurate guidance
- **Source Verification Support**: I maintain conversation flow while being completely transparent about my information sources, enabling you to verify claims and explore source materials independently
- **Context Preservation**: I consider the broader business context and implications when providing information, not just narrow technical answers
- **Sensitive Information Awareness**: I'm designed to recognize when information might be confidential or sensitive and handle such content appropriately

## Slack Integration Behaviors:
- **Seamless Thread Participation**: I automatically participate in threads once mentioned - you don't need to @mention me again within the same conversation thread
- **Real-Time Feedback**: I show typing indicators while processing your requests so you know I'm actively working on your query
- **Universal Accessibility**: I work consistently across all Slack contexts including direct messages, public channels, private channels, and group conversations
- **Conversation History Integration**: I can reference and build upon previous messages in ongoing threads to maintain conversational continuity
- **Multi-User Thread Handling**: In group conversations, I can distinguish between different participants and maintain context for multiple concurrent discussion threads

## Advanced Features:
- **Document Upload Analysis**: When you upload documents directly to our conversation, I can immediately analyze their contents and answer questions about them without requiring separate ingestion processes
- **Comparative Analysis**: I can compare information across multiple documents or data sources to identify discrepancies, patterns, or complementary insights
- **Workflow Integration**: I can suggest next steps, related documents, or additional resources based on the context of your queries and available organizational knowledge
- **Knowledge Gap Identification**: I can identify areas where your knowledge base might benefit from additional documentation or information gathering

My core strength lies in efficiently connecting you with your organization's documented knowledge while providing intelligent, contextual assistance tailored to your specific business needs and strategic objectives. I'm designed to enhance your productivity by serving as an always-available, comprehensive gateway to your organizational intelligence."""

# Constants
HTTP_OK = 200


async def extract_pdf_text(pdf_content: bytes, file_name: str) -> str:
    """Extract text from PDF using PyMuPDF and chunk for embedding compatibility"""
    if not PYMUPDF_AVAILABLE:
        logger.error("PyMuPDF not available for PDF processing")
        return f"[PDF file: {file_name} - PyMuPDF library not available]"

    try:
        from services.embedding_service import chunk_text

        # Open PDF from bytes
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
        text_content = ""

        for page_num in range(pdf_document.page_count):
            page = pdf_document.load_page(page_num)
            page_text = page.get_text()
            if page_text.strip():
                text_content += f"\n\n--- Page {page_num + 1} ---\n{page_text}"

        pdf_document.close()

        if text_content.strip():
            full_text = text_content.strip()

            # If content is too long, chunk it to prevent embedding failures
            # Conservative limit: 6000 chars ≈ 1500 tokens (well under 8192 limit)
            if len(full_text) > 6000:
                logger.info(
                    f"PDF content is {len(full_text)} chars, chunking for embedding compatibility"
                )
                chunks = chunk_text(full_text, chunk_size=6000, chunk_overlap=200)
                # Return first chunk with indicator
                chunked_content = chunks[0]
                if len(chunks) > 1:
                    chunked_content += (
                        f"\n\n[Note: This is chunk 1 of {len(chunks)} from {file_name}]"
                    )
                return chunked_content
            else:
                return full_text
        else:
            return f"[PDF file: {file_name} - No extractable text content found]"

    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_name}: {e}")
        return f"[PDF file: {file_name} - Error extracting text: {str(e)}]"


async def extract_office_text(content: bytes, file_name: str, file_type: str) -> str:
    """Extract text from Office documents (Word, Excel, PowerPoint)"""
    try:
        content_stream = io.BytesIO(content)

        if file_name.endswith(".docx") or "wordprocessingml" in file_type:
            return await extract_word_text(content_stream, file_name)
        elif file_name.endswith(".xlsx") or "spreadsheetml" in file_type:
            return await extract_excel_text(content_stream, file_name)
        elif file_name.endswith(".pptx") or "presentationml" in file_type:
            return await extract_powerpoint_text(content_stream, file_name)
        else:
            return f"[Office document: {file_name} - Unsupported Office format]"

    except Exception as e:
        logger.error(f"Error extracting text from Office document {file_name}: {e}")
        return f"[Office document: {file_name} - Error extracting text: {str(e)}]"


async def extract_word_text(content_stream: io.BytesIO, file_name: str) -> str:
    """Extract text from Word documents"""
    if not PYTHON_DOCX_AVAILABLE:
        logger.error("python-docx not available for Word processing")
        return f"[Word document: {file_name} - python-docx library not available]"

    try:
        doc = Document(content_stream)
        text_content = ""

        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_content += paragraph.text + "\n"

        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    if cell.text.strip():
                        row_text.append(cell.text.strip())
                if row_text:
                    text_content += " | ".join(row_text) + "\n"

        if text_content.strip():
            return text_content.strip()
        else:
            return f"[Word document: {file_name} - No extractable text content found]"

    except Exception as e:
        logger.error(f"Error extracting text from Word document {file_name}: {e}")
        return f"[Word document: {file_name} - Error extracting text: {str(e)}]"


async def extract_excel_text(content_stream: io.BytesIO, file_name: str) -> str:
    """Extract text from Excel files"""
    if not OPENPYXL_AVAILABLE:
        logger.error("openpyxl not available for Excel processing")
        return f"[Excel file: {file_name} - openpyxl library not available]"

    try:
        workbook = load_workbook(content_stream, read_only=True, data_only=True)
        text_content = ""

        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            text_content += f"\n\n--- Sheet: {sheet_name} ---\n"

            # Extract data from used cells
            for row in sheet.iter_rows(values_only=True):
                row_data = []
                for cell_value in row:
                    if cell_value is not None:
                        row_data.append(str(cell_value))
                if row_data:
                    text_content += " | ".join(row_data) + "\n"

        workbook.close()

        if text_content.strip():
            return text_content.strip()
        else:
            return f"[Excel file: {file_name} - No extractable data found]"

    except Exception as e:
        logger.error(f"Error extracting text from Excel file {file_name}: {e}")
        return f"[Excel file: {file_name} - Error extracting text: {str(e)}]"


async def extract_powerpoint_text(content_stream: io.BytesIO, file_name: str) -> str:
    """Extract text from PowerPoint presentations"""
    if not PYTHON_PPTX_AVAILABLE:
        logger.error("python-pptx not available for PowerPoint processing")
        return f"[PowerPoint file: {file_name} - python-pptx library not available]"

    try:
        prs = Presentation(content_stream)
        text_content = ""

        for i, slide in enumerate(prs.slides):
            text_content += f"\n\n--- Slide {i + 1} ---\n"

            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    text_content += shape.text + "\n"

        if text_content.strip():
            return text_content.strip()
        else:
            return f"[PowerPoint file: {file_name} - No extractable text content found]"

    except Exception as e:
        logger.error(f"Error extracting text from PowerPoint file {file_name}: {e}")
        return f"[PowerPoint file: {file_name} - Error extracting text: {str(e)}]"


async def process_file_attachments(
    files: list[dict], slack_service: SlackService
) -> str:
    """Process file attachments and extract text content"""
    document_content = ""

    for file_info in files:
        try:
            file_name = file_info.get("name", "unknown")
            file_type = file_info.get("mimetype", "")
            file_size = file_info.get("size", 0)

            # Skip very large files (>100MB)
            if file_size > 100 * 1024 * 1024:
                logger.warning(f"Skipping large file: {file_name} ({file_size} bytes)")
                continue

            # Get file URL
            file_url = file_info.get("url_private")
            if not file_url:
                logger.warning(f"No private URL for file: {file_name}")
                continue

            logger.info(
                f"Processing file: {file_name} ({file_type}, {file_size} bytes)"
            )

            # Download file content
            headers = {"Authorization": f"Bearer {slack_service.settings.bot_token}"}
            response = requests.get(file_url, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.error(
                    f"Failed to download file {file_name}: {response.status_code}"
                )
                continue

            file_content = ""

            # Process based on file type
            # Check MIME types first, then fall back to extensions
            if (
                file_type.startswith("text/")
                or file_type in ("text/vtt", "application/x-subrip", "text/srt")
                or file_name.endswith(
                    (".txt", ".md", ".py", ".js", ".json", ".csv", ".vtt", ".srt")
                )
            ):
                # Text files
                try:
                    file_content = response.text
                except UnicodeDecodeError:
                    file_content = response.content.decode("utf-8", errors="ignore")

            elif file_type == "application/pdf" or file_name.endswith(".pdf"):
                # PDF text extraction using PyMuPDF
                file_content = await extract_pdf_text(response.content, file_name)

            elif file_type.startswith(
                "application/vnd.openxmlformats"
            ) or file_name.endswith((".docx", ".xlsx", ".pptx")):
                # Office documents
                file_content = await extract_office_text(
                    response.content, file_name, file_type
                )

            else:
                # Unknown file type
                file_content = f"[File: {file_name} ({file_type}) - content extraction not supported for this file type.]"

            if file_content:
                document_content += f"\n\n--- Content from {file_name} ---\n{file_content}\n--- End of {file_name} ---"

        except Exception as e:
            logger.error(
                f"Error processing file {file_info.get('name', 'unknown')}: {e}"
            )
            continue

    return document_content.strip()


def get_user_system_prompt() -> str:
    """Get the default system prompt"""
    return DEFAULT_SYSTEM_MESSAGE


async def handle_message(
    text: str,
    user_id: str,
    slack_service: SlackService,
    llm_service: LLMService,
    channel: str,
    thread_ts: str | None = None,
    files: list[dict] | None = None,
    conversation_cache=None,
):
    """Handle an incoming message from Slack"""
    start_time = time.time()

    logger.info(
        "Processing user message",
        extra={
            "user_message": text,
            "user_id": user_id,
            "channel_id": channel,
            "thread_ts": thread_ts,
            "event_type": "user_message",
        },
    )

    # Record message processing metric
    metrics_service = get_metrics_service()
    if metrics_service:
        metrics_service.record_message_processed(
            user_id=user_id, channel_type="dm" if channel.startswith("D") else "channel"
        )

        # Track active conversations with proper conversation ID
        # Use thread_ts for threaded conversations, otherwise use channel
        # This matches the conversation_id used by LLM service for Langfuse tracing
        conversation_id = thread_ts or channel
        metrics_service.record_conversation_activity(conversation_id)

        # Categorize query type for metrics
        query_category = "question"  # Default
        if text.lower().startswith(("run ", "execute ", "start ")):
            query_category = "command"
        elif thread_ts:  # In a thread, likely continuing conversation
            query_category = "conversation"

        has_context = bool(thread_ts)  # Has conversation context
        metrics_service.record_query_type(query_category, has_context)

    # For tracking the thinking indicator message
    thinking_message_ts = None

    try:
        # Show typing indicator (skip if method doesn't exist)
        # Note: Typing indicators are handled by Slack automatically in most cases

        # Handle agent process commands
        if text.strip().lower().startswith("start "):
            agent_process_name = text.strip().lower()[6:]
            if agent_process_name:
                logger.info(f"Starting agent process: {agent_process_name}")

                try:
                    # First send thinking message
                    thinking_message_ts = await slack_service.send_thinking_indicator(
                        channel, thread_ts
                    )

                    # Run the agent process
                    response = await run_agent_process(
                        process_name=agent_process_name,
                        slack_service=slack_service,
                        channel_id=channel,
                        thread_ts=thread_ts,
                    )

                    # Clean up thinking message before sending response
                    if thinking_message_ts:
                        try:
                            await slack_service.delete_thinking_indicator(
                                channel, thinking_message_ts
                            )
                            thinking_message_ts = None
                        except Exception as e:
                            logger.warning(f"Error deleting thinking message: {e}")

                    # Send response with agent blocks
                    formatted_response = await MessageFormatter.format_message(response)
                    agent_blocks = get_agent_blocks()

                    await slack_service.send_message(
                        channel=channel,
                        text=formatted_response,
                        blocks=agent_blocks,
                        thread_ts=thread_ts,
                    )

                except Exception as e:
                    # Clean up thinking message on error
                    if thinking_message_ts:
                        with contextlib.suppress(Exception):
                            await slack_service.delete_thinking_indicator(
                                channel, thinking_message_ts
                            )

                    logger.error(f"Agent process failed: {e}")
                    error_response = (
                        f"❌ Agent process '{agent_process_name}' failed: {str(e)}"
                    )
                    await slack_service.send_message(
                        channel=channel, text=error_response, thread_ts=thread_ts
                    )
                return

        # Regular LLM response handling
        try:
            # First send thinking message
            thinking_message_ts = await slack_service.send_thinking_indicator(
                channel, thread_ts
            )
        except Exception as e:
            logger.error(f"Error posting thinking message: {e}")

        # Handle file attachments
        document_content = ""
        if files:
            logger.info(f"Files attached: {[f.get('name', 'unknown') for f in files]}")
            document_content = await process_file_attachments(files, slack_service)
            if document_content:
                logger.info(
                    f"Extracted {len(document_content)} characters from {len(files)} file(s)"
                )

        # Get the thread history for context
        history, should_use_thread_context = await slack_service.get_thread_history(
            channel, thread_ts
        )

        if should_use_thread_context:
            logger.info(
                f"Using thread context with {len(history)} messages for response generation"
            )

        # Add document reference to cache if present and cache is available
        if document_content and conversation_cache and thread_ts:
            # Create a concise summary for chat history instead of full content
            file_names = (
                [f.get("name", "unknown") for f in files] if files else ["document"]
            )
            file_summary = f"[User shared {len(file_names)} file(s): {', '.join(file_names)} - content processed and analyzed]"

            document_message = {
                "role": "user",
                "content": file_summary,
            }
            await conversation_cache.update_conversation(
                thread_ts, document_message, is_bot_message=False
            )
            logger.info(
                f"Added document reference to conversation cache for thread {thread_ts}: {file_names}"
            )

        # Generate response using LLM service with document-aware RAG
        response = await llm_service.get_response(
            messages=history,
            user_id=user_id,
            current_query=text,
            document_content=document_content if document_content else None,
            document_filename=files[0].get("name")
            if files and document_content
            else None,
        )

        # Clean up thinking message
        if thinking_message_ts:
            try:
                await slack_service.delete_thinking_indicator(
                    channel, thinking_message_ts
                )
            except Exception as e:
                logger.warning(f"Error deleting thinking message: {e}")

        # Format and send the response
        if response:
            formatted_response = await MessageFormatter.format_message(response)
            await slack_service.send_message(
                channel=channel, text=formatted_response, thread_ts=thread_ts
            )
        else:
            await slack_service.send_message(
                channel=channel,
                text="I apologize, but I couldn't generate a response. Please try again.",
                thread_ts=thread_ts,
            )

        # Record successful request timing
        if metrics_service:
            duration = time.time() - start_time
            metrics_service.request_duration.labels(
                endpoint="message_handler", method="POST"
            ).observe(duration)

    except Exception as e:
        # Clean up thinking message on error
        if thinking_message_ts:
            with contextlib.suppress(Exception):
                await slack_service.delete_thinking_indicator(
                    channel, thinking_message_ts
                )

        await handle_error(
            slack_service.client,
            channel,
            thread_ts,
            e,
            "I'm sorry, I encountered an error while processing your message.",
        )
