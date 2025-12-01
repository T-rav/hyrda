"""Pagination utilities for list endpoints."""

from typing import Any

from flask import request
from sqlalchemy.orm import Query


def get_pagination_params(
    default_per_page: int = 50,
    max_per_page: int = 100
) -> tuple[int, int]:
    """Get pagination parameters from request query string.

    Args:
        default_per_page: Default items per page (default: 50)
        max_per_page: Maximum items per page (default: 100)

    Returns:
        Tuple of (page, per_page) where:
        - page: 1-indexed page number (minimum 1)
        - per_page: items per page (capped at max_per_page)

    Examples:
        >>> # Request: /api/users?page=2&per_page=25
        >>> get_pagination_params()
        (2, 25)
        >>> # Request: /api/users (no params)
        >>> get_pagination_params()
        (1, 50)
        >>> # Request: /api/users?page=0&per_page=200
        >>> get_pagination_params(max_per_page=100)
        (1, 100)  # page=0 becomes 1, per_page=200 capped to 100
    """
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(request.args.get("per_page", default_per_page))
        per_page = max(1, min(per_page, max_per_page))
    except (ValueError, TypeError):
        per_page = default_per_page

    return page, per_page


def paginate_query(
    query: Query,
    page: int,
    per_page: int
) -> tuple[list[Any], int]:
    """Paginate a SQLAlchemy query.

    Args:
        query: SQLAlchemy query to paginate
        page: 1-indexed page number
        per_page: Number of items per page

    Returns:
        Tuple of (items, total_count) where:
        - items: List of items for the requested page
        - total_count: Total number of items across all pages

    Example:
        >>> query = session.query(User)
        >>> items, total = paginate_query(query, page=2, per_page=25)
        >>> # Returns items 26-50 and total count
    """
    total_count = query.count()

    # Calculate offset
    offset = (page - 1) * per_page

    # Get items for this page
    items = query.offset(offset).limit(per_page).all()

    return items, total_count


def build_pagination_response(
    items: list[Any],
    total_count: int,
    page: int,
    per_page: int
) -> dict[str, Any]:
    """Build a standardized pagination response.

    Args:
        items: List of items for the current page
        total_count: Total number of items across all pages
        page: Current page number (1-indexed)
        per_page: Items per page

    Returns:
        Dictionary with pagination metadata:
        - items: The actual data items
        - pagination: Metadata about pagination state

    Example:
        >>> response = build_pagination_response(users, 150, 2, 50)
        >>> response
        {
            "items": [...],
            "pagination": {
                "page": 2,
                "per_page": 50,
                "total": 150,
                "total_pages": 3,
                "has_prev": True,
                "has_next": True
            }
        }
    """
    total_pages = (total_count + per_page - 1) // per_page  # Ceiling division

    return {
        "items": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total_count,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages
        }
    }
