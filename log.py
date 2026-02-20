"""Structured JSON logging for Hydra."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info and record.exc_info[1] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        # Merge extra fields injected by adapters
        for key in ("issue", "worker", "pr", "phase", "batch"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        return json.dumps(entry, default=str)


def setup_logging(
    *,
    level: int = logging.INFO,
    json_output: bool = True,
) -> logging.Logger:
    """Configure the ``hydra`` logger.

    Parameters
    ----------
    level:
        Logging level.
    json_output:
        If *True*, use JSON formatting; otherwise plain text.

    Returns
    -------
    logging.Logger
        The configured root ``hydra`` logger.
    """
    logger = logging.getLogger("hydra")
    logger.setLevel(level)
    logger.handlers.clear()

    formatter: logging.Formatter
    if json_output:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger
