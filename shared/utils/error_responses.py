"""Standardized error response formats for all services.

Provides consistent error structures across bot, agent-service, control-plane, and tasks services.
"""

from typing import Any


class ErrorCode:
    """Standard error codes used across all services."""

    # Authentication & Authorization (40x)
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    SESSION_EXPIRED = "SESSION_EXPIRED"

    # Validation (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    INVALID_FORMAT = "INVALID_FORMAT"

    # Resource (404, 409)
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"

    # Server (500, 503)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"


def error_response(
    message: str,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a standardized error response.

    Args:
        message: Human-readable error message
        error_code: Machine-readable error code (from ErrorCode class)
        details: Optional additional context (debug info, validation errors, etc.)

    Returns:
        Standardized error response dictionary

    Examples:
        >>> error_response("User not found", ErrorCode.NOT_FOUND)
        {'error': 'User not found', 'error_code': 'NOT_FOUND'}

        >>> error_response(
        ...     "Validation failed",
        ...     ErrorCode.VALIDATION_ERROR,
        ...     {"field": "email", "reason": "Invalid format"}
        ... )
        {'error': 'Validation failed', 'error_code': 'VALIDATION_ERROR',
         'details': {'field': 'email', 'reason': 'Invalid format'}}
    """
    response: dict[str, Any] = {"error": message}

    if error_code:
        response["error_code"] = error_code

    if details:
        response["details"] = details

    return response


def validation_error(
    message: str, field: str | None = None, **kwargs: Any
) -> dict[str, Any]:
    """Create a validation error response.

    Args:
        message: Error message
        field: Field name that failed validation
        **kwargs: Additional context

    Returns:
        Standardized validation error response

    Examples:
        >>> validation_error("Email is required", field="email")
        {'error': 'Email is required', 'error_code': 'VALIDATION_ERROR',
         'details': {'field': 'email'}}
    """
    details = kwargs.copy()
    if field:
        details["field"] = field

    return error_response(
        message, ErrorCode.VALIDATION_ERROR, details if details else None
    )


def not_found_error(resource: str, identifier: str | None = None) -> dict[str, Any]:
    """Create a not found error response.

    Args:
        resource: Type of resource (e.g., "User", "Agent", "Job")
        identifier: Optional identifier that wasn't found

    Returns:
        Standardized not found error response

    Examples:
        >>> not_found_error("Agent", "profile")
        {'error': "Agent 'profile' not found", 'error_code': 'NOT_FOUND'}

        >>> not_found_error("User")
        {'error': 'User not found', 'error_code': 'NOT_FOUND'}
    """
    if identifier:
        message = f"{resource} '{identifier}' not found"
    else:
        message = f"{resource} not found"

    return error_response(message, ErrorCode.NOT_FOUND)


def unauthorized_error(message: str = "Not authenticated") -> dict[str, Any]:
    """Create an unauthorized error response.

    Args:
        message: Error message

    Returns:
        Standardized unauthorized error response

    Examples:
        >>> unauthorized_error()
        {'error': 'Not authenticated', 'error_code': 'UNAUTHORIZED'}
    """
    return error_response(message, ErrorCode.UNAUTHORIZED)


def forbidden_error(message: str = "Access denied") -> dict[str, Any]:
    """Create a forbidden error response.

    Args:
        message: Error message

    Returns:
        Standardized forbidden error response

    Examples:
        >>> forbidden_error("Only admins can perform this action")
        {'error': 'Only admins can perform this action', 'error_code': 'FORBIDDEN'}
    """
    return error_response(message, ErrorCode.FORBIDDEN)


def internal_error(
    message: str = "Internal server error", details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Create an internal server error response.

    Args:
        message: Error message
        details: Optional error details (use for debugging, not user-facing info)

    Returns:
        Standardized internal error response

    Examples:
        >>> internal_error("Database connection failed")
        {'error': 'Database connection failed', 'error_code': 'INTERNAL_ERROR'}
    """
    return error_response(message, ErrorCode.INTERNAL_ERROR, details)


def service_unavailable_error(service: str) -> dict[str, Any]:
    """Create a service unavailable error response.

    Args:
        service: Name of the unavailable service

    Returns:
        Standardized service unavailable error response

    Examples:
        >>> service_unavailable_error("agent-service")
        {'error': 'Service unavailable: agent-service', 'error_code': 'SERVICE_UNAVAILABLE'}
    """
    return error_response(
        f"Service unavailable: {service}", ErrorCode.SERVICE_UNAVAILABLE
    )
