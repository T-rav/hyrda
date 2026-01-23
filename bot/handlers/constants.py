"""Constants for message and file processing.

Centralizes magic numbers and configuration values for maintainability.
"""

# File processing limits
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100MB - Maximum file size to process
FILE_DOWNLOAD_TIMEOUT_SECONDS = 600  # 10 minutes for large file downloads

# Embedding and chunking limits
MAX_EMBEDDING_CHARS = (
    6000  # Conservative limit for text-embedding-3-small (8192 tokens)
)
CHUNK_OVERLAP_CHARS = 200  # Overlap size for context continuity between chunks

# Text extraction limits
MAX_EXTRACTED_TEXT_LENGTH = 50000  # Maximum characters from a single file

# Conversation and thread limits
MAX_THREAD_MESSAGES = 50  # Maximum messages to retrieve from thread history
CONVERSATION_CACHE_TTL_SECONDS = 3600  # 1 hour cache for document content

# Message formatting
MAX_SLACK_MESSAGE_LENGTH = 40000  # Slack's max message size
THINKING_INDICATOR_UPDATE_INTERVAL = 2  # Seconds between status updates

# Query processing
MIN_QUERY_LENGTH = 3  # Minimum characters for valid query
MAX_QUERY_LENGTH = 10000  # Maximum query length to process
