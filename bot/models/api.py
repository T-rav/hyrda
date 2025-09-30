"""API response models"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import Field


@dataclass(frozen=True)
class ApiResponse:
    """Generic API response wrapper."""

    success: bool
    data: Any | None = None
    error_message: str | None = None
    error_code: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
