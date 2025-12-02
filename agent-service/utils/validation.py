"""Input validation utilities for API requests."""

import html
import re
from typing import Any


def validate_agent_name(name: str | None) -> tuple[bool, str | None]:
    """Validate agent name format and constraints.

    Rules:
    - Required (not None or empty)
    - Length: 1-50 characters
    - Format: lowercase alphanumeric, hyphens, underscores
    - Must start with letter
    - No consecutive special characters

    Args:
        name: The agent name to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if valid
        - (False, error_message) if invalid

    Examples:
        >>> validate_agent_name("profile")
        (True, None)
        >>> validate_agent_name("company-profile")
        (True, None)
        >>> validate_agent_name("Invalid Name")
        (False, "Agent name must be lowercase alphanumeric...")
    """
    if not name:
        return False, "Agent name is required"

    if not isinstance(name, str):
        return False, "Agent name must be a string"

    if len(name) < 1:
        return False, "Agent name cannot be empty"

    if len(name) > 50:
        return False, "Agent name must be 50 characters or less"

    # Must start with letter
    if not name[0].isalpha():
        return False, "Agent name must start with a letter"

    # Only lowercase alphanumeric, hyphens, underscores
    if not re.match(r"^[a-z][a-z0-9_-]*$", name):
        return False, "Agent name must be lowercase alphanumeric with hyphens or underscores only"

    # No consecutive special characters
    if "--" in name or "__" in name or "-_" in name or "_-" in name:
        return False, "Agent name cannot contain consecutive special characters"

    return True, None


def validate_group_name(name: str | None) -> tuple[bool, str | None]:
    """Validate group name format and constraints.

    Rules:
    - Required (not None or empty)
    - Length: 1-50 characters
    - Format: lowercase alphanumeric, hyphens, underscores
    - Must start with letter
    - No consecutive special characters

    Args:
        name: The group name to validate

    Returns:
        Tuple of (is_valid, error_message)

    Examples:
        >>> validate_group_name("engineering")
        (True, None)
        >>> validate_group_name("all_users")
        (True, None)
        >>> validate_group_name("Invalid Group!")
        (False, "Group name must be lowercase alphanumeric...")
    """
    if not name:
        return False, "Group name is required"

    if not isinstance(name, str):
        return False, "Group name must be a string"

    if len(name) < 1:
        return False, "Group name cannot be empty"

    if len(name) > 50:
        return False, "Group name must be 50 characters or less"

    # Must start with letter
    if not name[0].isalpha():
        return False, "Group name must start with a letter"

    # Only lowercase alphanumeric, hyphens, underscores
    if not re.match(r"^[a-z][a-z0-9_-]*$", name):
        return False, "Group name must be lowercase alphanumeric with hyphens or underscores only"

    # No consecutive special characters
    if "--" in name or "__" in name or "-_" in name or "_-" in name:
        return False, "Group name cannot contain consecutive special characters"

    return True, None


def validate_display_name(name: str | None, max_length: int = 100) -> tuple[bool, str | None]:
    """Validate display name format and constraints.

    Rules:
    - Optional (can be None or empty)
    - Length: 1-max_length characters (default 100)
    - Must not be only whitespace

    Args:
        name: The display name to validate
        max_length: Maximum allowed length (default: 100)

    Returns:
        Tuple of (is_valid, error_message)

    Examples:
        >>> validate_display_name("Company Profile Agent")
        (True, None)
        >>> validate_display_name("   ")
        (False, "Display name cannot be only whitespace")
        >>> validate_display_name("A" * 101)
        (False, "Display name must be 100 characters or less")
    """
    # Display name is optional
    if name is None or name == "":
        return True, None

    if not isinstance(name, str):
        return False, "Display name must be a string"

    # Cannot be only whitespace
    if name.strip() == "":
        return False, "Display name cannot be only whitespace"

    if len(name) > max_length:
        return False, f"Display name must be {max_length} characters or less"

    return True, None


def validate_email(email: str | None) -> tuple[bool, str | None]:
    """Validate email address format.

    More robust email validation with additional checks.
    Not comprehensive RFC 5322 validation but catches common issues.

    Args:
        email: The email address to validate

    Returns:
        Tuple of (is_valid, error_message)

    Examples:
        >>> validate_email("user@example.com")
        (True, None)
        >>> validate_email("invalid-email")
        (False, "Invalid email format")
    """
    if not email:
        return False, "Email is required"

    if not isinstance(email, str):
        return False, "Email must be a string"

    # More robust email pattern
    # - Must start with alphanumeric
    # - Local part can contain dots, underscores, percent, plus, hyphen
    # - Domain must have valid structure
    # - TLD must be at least 2 characters
    email_pattern = r"^[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$"

    if not re.match(email_pattern, email):
        return False, "Invalid email format"

    # Check for consecutive dots (not allowed)
    if ".." in email:
        return False, "Invalid email format (consecutive dots)"

    # Check length
    if len(email) > 255:
        return False, "Email must be 255 characters or less"

    # Check local and domain parts separately
    parts = email.split("@")
    if len(parts) != 2:
        return False, "Invalid email format"

    local_part, domain_part = parts

    # Local part max 64 characters
    if len(local_part) > 64:
        return False, "Email local part too long (max 64 characters)"

    # Domain part max 255 characters
    if len(domain_part) > 255:
        return False, "Email domain too long (max 255 characters)"

    return True, None


def validate_required_field(value: Any, field_name: str) -> tuple[bool, str | None]:
    """Validate that a required field is present and not empty.

    Args:
        value: The value to validate
        field_name: Name of the field for error messages

    Returns:
        Tuple of (is_valid, error_message)

    Examples:
        >>> validate_required_field("value", "name")
        (True, None)
        >>> validate_required_field(None, "name")
        (False, "name is required")
        >>> validate_required_field("", "name")
        (False, "name is required")
    """
    if value is None:
        return False, f"{field_name} is required"

    if isinstance(value, str) and value.strip() == "":
        return False, f"{field_name} is required"

    return True, None


def sanitize_text_input(text: str | None, max_length: int = 1000) -> str:
    """Sanitize text input to prevent XSS and injection attacks.

    Removes HTML tags and limits length. Use for user-provided text
    that will be stored and displayed.

    Args:
        text: The text to sanitize
        max_length: Maximum allowed length (default: 1000)

    Returns:
        Sanitized text string

    Examples:
        >>> sanitize_text_input("<script>alert('xss')</script>Hello")
        "Hello"
        >>> sanitize_text_input("Normal text")
        "Normal text"
    """
    if not text:
        return ""

    if not isinstance(text, str):
        text = str(text)

    # Escape HTML entities to prevent XSS
    sanitized = html.escape(text)

    # Trim to max length
    sanitized = sanitized[:max_length]

    # Remove any remaining control characters
    sanitized = "".join(char for char in sanitized if ord(char) >= 32 or char in "\n\r\t")

    return sanitized.strip()
