"""Shared utility functions."""

from .error_responses import (
    ErrorCode,
    error_response,
    forbidden_error,
    internal_error,
    not_found_error,
    service_unavailable_error,
    unauthorized_error,
    validation_error,
)
from .log_sanitizer import (
    safe_repr,
    sanitize_dict,
    sanitize_log_record,
    sanitize_string,
)

__all__ = [
    # Log sanitization
    "sanitize_string",
    "sanitize_dict",
    "sanitize_log_record",
    "safe_repr",
    # Error responses
    "ErrorCode",
    "error_response",
    "validation_error",
    "not_found_error",
    "unauthorized_error",
    "forbidden_error",
    "internal_error",
    "service_unavailable_error",
]
