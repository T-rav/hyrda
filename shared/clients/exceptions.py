"""Custom exceptions for retrieval client."""


class RetrievalError(Exception):
    """Base exception for retrieval errors."""

    pass


class RetrievalAuthError(RetrievalError):
    """Authentication failed - invalid or missing service token."""

    def __init__(self, message: str = "Invalid service token"):
        super().__init__(message)
        self.message = message


class RetrievalTimeoutError(RetrievalError):
    """Request timed out waiting for rag-service response."""

    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Request timed out after {timeout_seconds}s")


class RetrievalValidationError(RetrievalError):
    """Invalid request parameters."""

    def __init__(self, message: str):
        super().__init__(f"Validation error: {message}")
        self.message = message


class RetrievalServiceError(RetrievalError):
    """Rag-service returned an error response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Service error {status_code}: {detail}")


class RetrievalConnectionError(RetrievalError):
    """Cannot connect to rag-service."""

    def __init__(self, base_url: str, original_error: Exception):
        self.base_url = base_url
        self.original_error = original_error
        super().__init__(f"Cannot connect to {base_url}: {original_error}")
