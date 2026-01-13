"""Error handling utilities for consistent API responses."""

from typing import Any

from fastapi.responses import JSONResponse


def error_response(
    message: str,
    status_code: int = 400,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Create a standardized error response.

    Args:
        message: Human-readable error message
        status_code: HTTP status code (default: 400)
        error_code: Optional machine-readable error code (e.g., "AGENT_NOT_FOUND")
        details: Optional additional error details (e.g., validation errors)

    Returns:
        JSONResponse for FastAPI to return

    Examples:
        # FastAPI JSONResponse pattern
        return error_response("Agent not found", 404, "AGENT_NOT_FOUND")

        # With additional details
        return error_response(
            "Validation failed",
            400,
            "VALIDATION_ERROR",
            {"fields": {"name": "Too short"}}
        )

        # Alternative: Use HTTPException directly for FastAPI
        # raise HTTPException(status_code=404, detail="Agent not found")
    """
    response_data: dict[str, Any] = {
        "error": message,
        "status": status_code,
    }

    if error_code:
        response_data["error_code"] = error_code

    if details:
        response_data["details"] = details

    return JSONResponse(content=response_data, status_code=status_code)


def success_response(
    data: dict[str, Any] | None = None,
    message: str | None = None,
    status_code: int = 200,
) -> JSONResponse:
    """Create a standardized success response.

    Args:
        data: Response data to include
        message: Optional success message
        status_code: HTTP status code (default: 200)

    Returns:
        JSONResponse for FastAPI to return

    Examples:
        # FastAPI JSONResponse pattern with data
        return success_response({"agent_name": "profile"})

        # With success message
        return success_response(message="Agent deleted successfully")
    """
    response_data: dict[str, Any] = {"success": True}

    if data:
        response_data.update(data)

    if message:
        response_data["message"] = message

    return JSONResponse(content=response_data, status_code=status_code)
