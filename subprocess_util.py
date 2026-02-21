"""Shared async subprocess helper for Hydra."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from pathlib import Path

logger = logging.getLogger("hydra.subprocess")


class AuthenticationError(RuntimeError):
    """Raised when a subprocess fails due to GitHub authentication issues."""


class SubprocessTimeoutError(RuntimeError):
    """Raised when a subprocess exceeds its allowed execution time."""


_AUTH_PATTERNS = ("401", "not logged in", "authentication required", "auth token")


def _is_auth_error(stderr: str) -> bool:
    """Check if stderr indicates a GitHub authentication failure."""
    stderr_lower = stderr.lower()
    return any(p in stderr_lower for p in _AUTH_PATTERNS)


def make_clean_env(gh_token: str = "") -> dict[str, str]:
    """Build a subprocess env dict with ``CLAUDECODE`` stripped.

    When *gh_token* is non-empty it is injected as ``GH_TOKEN``.
    """
    env = {**os.environ}
    env.pop("CLAUDECODE", None)
    if gh_token:
        env["GH_TOKEN"] = gh_token
    return env


async def run_subprocess(
    *cmd: str,
    cwd: Path | None = None,
    gh_token: str = "",
    timeout: float = 120.0,
) -> str:
    """Run a subprocess and return stripped stdout.

    Strips the ``CLAUDECODE`` key from the environment to prevent
    nesting detection.  When *gh_token* is non-empty it is injected
    as ``GH_TOKEN``.

    Raises :class:`SubprocessTimeoutError` if the command exceeds *timeout* seconds.
    Raises :class:`RuntimeError` on non-zero exit.
    """
    env = make_clean_env(gh_token)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise SubprocessTimeoutError(
            f"Command {cmd!r} timed out after {timeout}s"
        ) from None
    if proc.returncode != 0:
        stderr_text = stderr.decode().strip()
        msg = f"Command {cmd!r} failed (rc={proc.returncode}): {stderr_text}"
        if _is_auth_error(stderr_text):
            raise AuthenticationError(msg)
        raise RuntimeError(msg)
    return stdout.decode().strip()


_RETRYABLE_PATTERNS = (
    "rate limit",
    "timeout",
    "timed out",
    "connection",
    "502",
    "503",
    "504",
)
_NON_RETRYABLE_PATTERNS = ("401", "403", "404")


def _is_retryable_error(stderr: str) -> bool:
    """Check if a subprocess error indicates a transient/retryable condition."""
    stderr_lower = stderr.lower()
    for pattern in _NON_RETRYABLE_PATTERNS:
        if pattern in stderr_lower:
            # 403 with "rate limit" IS retryable
            if pattern == "403" and "rate limit" in stderr_lower:
                continue
            return False
    return any(p in stderr_lower for p in _RETRYABLE_PATTERNS)


async def run_subprocess_with_retry(
    *cmd: str,
    cwd: Path | None = None,
    gh_token: str = "",
    max_retries: int = 3,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 30.0,
    timeout: float = 120.0,
) -> str:
    """Run a subprocess with exponential backoff retry on transient errors.

    Retries on: rate-limit, timeout, connection errors, 502/503/504.
    Does NOT retry on: auth (401), forbidden (403 without rate-limit), not-found (404).

    Raises :class:`RuntimeError` after all retries are exhausted.
    """
    last_error: RuntimeError | None = None
    for attempt in range(max_retries + 1):
        try:
            return await run_subprocess(
                *cmd, cwd=cwd, gh_token=gh_token, timeout=timeout
            )
        except RuntimeError as exc:
            if isinstance(exc, AuthenticationError):
                raise
            last_error = exc
            error_msg = str(exc)
            if attempt >= max_retries or not _is_retryable_error(error_msg):
                raise
            delay = min(base_delay_seconds * (2**attempt), max_delay_seconds)
            jitter = random.uniform(0, delay * 0.5)  # noqa: S311
            total_delay = delay + jitter
            logger.warning(
                "Retryable error (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                max_retries,
                total_delay,
                error_msg[:200],
            )
            await asyncio.sleep(total_delay)
    # Should not reach here, but satisfy type checker
    assert last_error is not None  # noqa: S101
    raise last_error
