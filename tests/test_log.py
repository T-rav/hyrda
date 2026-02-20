"""Tests for log.py."""

from __future__ import annotations

import inspect
import json
import logging
from collections.abc import Generator

import pytest

from log import JSONFormatter, setup_logging

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_hydra_logger() -> Generator[None, None, None]:
    """Clear the hydra logger's handlers before and after each test."""
    logger = logging.getLogger("hydra")
    logger.handlers.clear()
    yield
    logger.handlers.clear()


def _make_record(
    msg: str = "hello",
    level: int = logging.INFO,
    name: str = "hydra",
) -> logging.LogRecord:
    """Create a minimal LogRecord for testing."""
    return logging.LogRecord(
        name=name,
        level=level,
        pathname="test.py",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


# ---------------------------------------------------------------------------
# JSONFormatter
# ---------------------------------------------------------------------------


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format_produces_valid_json_with_expected_keys(self) -> None:
        record = _make_record("test message")
        output = JSONFormatter().format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["msg"] == "test message"
        assert parsed["logger"] == "hydra"
        assert "ts" in parsed

    def test_format_includes_exception_info(self) -> None:
        record = _make_record("boom")
        try:
            raise ValueError("kaboom")
        except ValueError:
            import sys

            record.exc_info = sys.exc_info()

        output = JSONFormatter().format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert "kaboom" in parsed["exception"]

    def test_format_includes_extra_fields_when_set(self) -> None:
        record = _make_record()
        record.issue = 42  # type: ignore[attr-defined]
        record.worker = "w-1"  # type: ignore[attr-defined]
        record.pr = 99  # type: ignore[attr-defined]
        record.phase = "plan"  # type: ignore[attr-defined]
        record.batch = "b-1"  # type: ignore[attr-defined]

        output = JSONFormatter().format(record)
        parsed = json.loads(output)

        assert parsed["issue"] == 42
        assert parsed["worker"] == "w-1"
        assert parsed["pr"] == 99
        assert parsed["phase"] == "plan"
        assert parsed["batch"] == "b-1"

    def test_format_omits_extra_fields_when_not_set(self) -> None:
        record = _make_record()
        output = JSONFormatter().format(record)
        parsed = json.loads(output)

        for key in ("issue", "worker", "pr", "phase", "batch"):
            assert key not in parsed


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------


class TestSetupLogging:
    """Tests for setup_logging()."""

    def test_returns_hydra_logger(self) -> None:
        logger = setup_logging()
        assert logger.name == "hydra"

    def test_json_output_uses_json_formatter(self) -> None:
        logger = setup_logging(json_output=True)
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0].formatter, JSONFormatter)

    def test_plain_output_uses_plain_formatter(self) -> None:
        logger = setup_logging(json_output=False)
        assert len(logger.handlers) == 1
        assert not isinstance(logger.handlers[0].formatter, JSONFormatter)

    def test_sets_correct_level(self) -> None:
        logger = setup_logging(level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_clears_existing_handlers(self) -> None:
        setup_logging()
        logger = setup_logging()
        assert len(logger.handlers) == 1

    def test_no_log_dir_parameter(self) -> None:
        """Regression guard: log_dir must not be a parameter."""
        sig = inspect.signature(setup_logging)
        assert "log_dir" not in sig.parameters
