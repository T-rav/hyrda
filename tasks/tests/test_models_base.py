"""Tests for database models base functionality."""

import contextlib

import pytest
from sqlalchemy.orm import Session

from models.base import (
    get_data_db_session,
    get_db_session,
    init_data_db,
    init_db,
)


@pytest.fixture(autouse=True)
def reset_database_globals():
    """Reset global database state before each test."""
    import models.base as base_module

    # Store original values
    original_engine = base_module._engine
    original_session_local = base_module._SessionLocal
    original_data_engine = base_module._data_engine
    original_data_session_local = base_module._DataSessionLocal

    # Reset to None
    base_module._engine = None
    base_module._SessionLocal = None
    base_module._data_engine = None
    base_module._DataSessionLocal = None

    yield

    # Cleanup: Close engines and reset
    if base_module._engine:
        base_module._engine.dispose()
    if base_module._data_engine:
        base_module._data_engine.dispose()

    base_module._engine = original_engine
    base_module._SessionLocal = original_session_local
    base_module._data_engine = original_data_engine
    base_module._DataSessionLocal = original_data_session_local
