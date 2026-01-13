"""Tests for standardized error response utilities."""

import pytest

from shared.utils.error_responses import (
    ErrorCode,
    error_response,
    forbidden_error,
    internal_error,
    not_found_error,
    service_unavailable_error,
    unauthorized_error,
    validation_error,
)


class TestErrorCode:
    """Test error code constants."""

    def test_auth_error_codes_exist(self):
        """Test that authentication error codes are defined."""
        assert ErrorCode.UNAUTHORIZED == "UNAUTHORIZED"
        assert ErrorCode.FORBIDDEN == "FORBIDDEN"
        assert ErrorCode.NOT_AUTHENTICATED == "NOT_AUTHENTICATED"
        assert ErrorCode.INVALID_CREDENTIALS == "INVALID_CREDENTIALS"
        assert ErrorCode.SESSION_EXPIRED == "SESSION_EXPIRED"

    def test_validation_error_codes_exist(self):
        """Test that validation error codes are defined."""
        assert ErrorCode.VALIDATION_ERROR == "VALIDATION_ERROR"
        assert ErrorCode.INVALID_INPUT == "INVALID_INPUT"
        assert ErrorCode.MISSING_PARAMETER == "MISSING_PARAMETER"
        assert ErrorCode.INVALID_FORMAT == "INVALID_FORMAT"

    def test_resource_error_codes_exist(self):
        """Test that resource error codes are defined."""
        assert ErrorCode.NOT_FOUND == "NOT_FOUND"
        assert ErrorCode.ALREADY_EXISTS == "ALREADY_EXISTS"
        assert ErrorCode.CONFLICT == "CONFLICT"

    def test_server_error_codes_exist(self):
        """Test that server error codes are defined."""
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"
        assert ErrorCode.SERVICE_UNAVAILABLE == "SERVICE_UNAVAILABLE"
        assert ErrorCode.DATABASE_ERROR == "DATABASE_ERROR"
        assert ErrorCode.EXTERNAL_API_ERROR == "EXTERNAL_API_ERROR"


class TestErrorResponse:
    """Test generic error response builder."""

    def test_basic_error_response(self):
        """Test basic error response without error code."""
        result = error_response("Something went wrong")

        assert result == {"error": "Something went wrong"}
        assert "error_code" not in result
        assert "details" not in result

    def test_error_response_with_code(self):
        """Test error response with error code."""
        result = error_response("Not found", ErrorCode.NOT_FOUND)

        assert result == {
            "error": "Not found",
            "error_code": "NOT_FOUND"
        }
        assert "details" not in result

    def test_error_response_with_details(self):
        """Test error response with details."""
        details = {"field": "email", "reason": "Invalid format"}
        result = error_response(
            "Validation failed",
            ErrorCode.VALIDATION_ERROR,
            details
        )

        assert result == {
            "error": "Validation failed",
            "error_code": "VALIDATION_ERROR",
            "details": {"field": "email", "reason": "Invalid format"}
        }

    def test_error_response_with_none_code(self):
        """Test error response explicitly passes None for error_code."""
        result = error_response("Error message", error_code=None)

        assert result == {"error": "Error message"}
        assert "error_code" not in result

    def test_error_response_with_none_details(self):
        """Test error response explicitly passes None for details."""
        result = error_response(
            "Error message",
            ErrorCode.INTERNAL_ERROR,
            details=None
        )

        assert result == {
            "error": "Error message",
            "error_code": "INTERNAL_ERROR"
        }
        assert "details" not in result


class TestValidationError:
    """Test validation error helper."""

    def test_validation_error_basic(self):
        """Test basic validation error."""
        result = validation_error("Email is required")

        assert result["error"] == "Email is required"
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "details" not in result

    def test_validation_error_with_field(self):
        """Test validation error with field."""
        result = validation_error("Email is required", field="email")

        assert result == {
            "error": "Email is required",
            "error_code": "VALIDATION_ERROR",
            "details": {"field": "email"}
        }

    def test_validation_error_with_kwargs(self):
        """Test validation error with additional context."""
        result = validation_error(
            "Invalid email format",
            field="email",
            pattern="^[a-z]+@[a-z]+\\.[a-z]+$",
            value="not-an-email"
        )

        assert result["error"] == "Invalid email format"
        assert result["error_code"] == "VALIDATION_ERROR"
        assert result["details"]["field"] == "email"
        assert result["details"]["pattern"] == "^[a-z]+@[a-z]+\\.[a-z]+$"
        assert result["details"]["value"] == "not-an-email"

    def test_validation_error_without_field_but_with_kwargs(self):
        """Test validation error with kwargs but no field."""
        result = validation_error(
            "Request too large",
            max_size=1024,
            actual_size=2048
        )

        assert result["error"] == "Request too large"
        assert result["error_code"] == "VALIDATION_ERROR"
        assert result["details"] == {
            "max_size": 1024,
            "actual_size": 2048
        }


class TestNotFoundError:
    """Test not found error helper."""

    def test_not_found_error_with_identifier(self):
        """Test not found error with resource identifier."""
        result = not_found_error("Agent", "profile")

        assert result == {
            "error": "Agent 'profile' not found",
            "error_code": "NOT_FOUND"
        }

    def test_not_found_error_without_identifier(self):
        """Test not found error without identifier."""
        result = not_found_error("User")

        assert result == {
            "error": "User not found",
            "error_code": "NOT_FOUND"
        }

    def test_not_found_error_various_resources(self):
        """Test not found error with various resource types."""
        assert not_found_error("Job", "123")["error"] == "Job '123' not found"
        assert not_found_error("Task", "abc-def")["error"] == "Task 'abc-def' not found"
        assert not_found_error("Document")["error"] == "Document not found"


class TestUnauthorizedError:
    """Test unauthorized error helper."""

    def test_unauthorized_error_default_message(self):
        """Test unauthorized error with default message."""
        result = unauthorized_error()

        assert result == {
            "error": "Not authenticated",
            "error_code": "UNAUTHORIZED"
        }

    def test_unauthorized_error_custom_message(self):
        """Test unauthorized error with custom message."""
        result = unauthorized_error("Invalid API key")

        assert result == {
            "error": "Invalid API key",
            "error_code": "UNAUTHORIZED"
        }


class TestForbiddenError:
    """Test forbidden error helper."""

    def test_forbidden_error_default_message(self):
        """Test forbidden error with default message."""
        result = forbidden_error()

        assert result == {
            "error": "Access denied",
            "error_code": "FORBIDDEN"
        }

    def test_forbidden_error_custom_message(self):
        """Test forbidden error with custom message."""
        result = forbidden_error("Only admins can perform this action")

        assert result == {
            "error": "Only admins can perform this action",
            "error_code": "FORBIDDEN"
        }


class TestInternalError:
    """Test internal server error helper."""

    def test_internal_error_default_message(self):
        """Test internal error with default message."""
        result = internal_error()

        assert result == {
            "error": "Internal server error",
            "error_code": "INTERNAL_ERROR"
        }
        assert "details" not in result

    def test_internal_error_custom_message(self):
        """Test internal error with custom message."""
        result = internal_error("Database connection failed")

        assert result == {
            "error": "Database connection failed",
            "error_code": "INTERNAL_ERROR"
        }
        assert "details" not in result

    def test_internal_error_with_details(self):
        """Test internal error with debugging details."""
        details = {
            "traceback": "File main.py, line 42",
            "error_type": "ConnectionError"
        }
        result = internal_error("Database connection failed", details=details)

        assert result == {
            "error": "Database connection failed",
            "error_code": "INTERNAL_ERROR",
            "details": {
                "traceback": "File main.py, line 42",
                "error_type": "ConnectionError"
            }
        }


class TestServiceUnavailableError:
    """Test service unavailable error helper."""

    def test_service_unavailable_error(self):
        """Test service unavailable error."""
        result = service_unavailable_error("agent-service")

        assert result == {
            "error": "Service unavailable: agent-service",
            "error_code": "SERVICE_UNAVAILABLE"
        }

    def test_service_unavailable_error_various_services(self):
        """Test service unavailable error with various service names."""
        result1 = service_unavailable_error("database")
        assert result1["error"] == "Service unavailable: database"

        result2 = service_unavailable_error("redis-cache")
        assert result2["error"] == "Service unavailable: redis-cache"

        result3 = service_unavailable_error("external-api")
        assert result3["error"] == "Service unavailable: external-api"


class TestIntegration:
    """Test error response integration scenarios."""

    def test_error_responses_are_json_serializable(self):
        """Test that all error responses can be JSON serialized."""
        import json

        errors = [
            error_response("Test error"),
            validation_error("Invalid", field="test"),
            not_found_error("User", "123"),
            unauthorized_error(),
            forbidden_error("No access"),
            internal_error("Server error", {"key": "value"}),
            service_unavailable_error("api")
        ]

        for error in errors:
            # Should not raise exception
            json_str = json.dumps(error)
            # Should deserialize back to same structure
            assert json.loads(json_str) == error

    def test_consistent_structure_across_helpers(self):
        """Test that all helpers return consistent structure."""
        errors = [
            validation_error("Test"),
            not_found_error("Resource"),
            unauthorized_error(),
            forbidden_error(),
            internal_error(),
            service_unavailable_error("service")
        ]

        for error in errors:
            # All should have error field
            assert "error" in error
            assert isinstance(error["error"], str)

            # All should have error_code field
            assert "error_code" in error
            assert isinstance(error["error_code"], str)
