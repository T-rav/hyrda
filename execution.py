"""Subprocess execution abstraction — host vs Docker (future)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class SimpleResult:
    """Result from a simple (non-streaming) subprocess execution."""

    stdout: str
    stderr: str
    returncode: int


@runtime_checkable
class SubprocessRunner(Protocol):
    """Protocol for executing subprocesses.

    Two implementations are planned:
    - ``HostRunner``: executes on the host via ``asyncio.create_subprocess_exec``
    - ``DockerRunner``: executes inside a Docker container (future)
    """

    async def create_streaming_process(
        self,
        cmd: Sequence[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        limit: int = 65536,
        start_new_session: bool = False,
    ) -> asyncio.subprocess.Process:
        """Create a subprocess with stdin/stdout/stderr pipes for streaming.

        The caller is responsible for writing to stdin, reading stdout,
        draining stderr, and managing the process lifecycle.
        """
        ...

    async def run_simple(
        self,
        cmd: Sequence[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 120.0,
    ) -> SimpleResult:
        """Run a command and return its output.

        Raises ``TimeoutError`` if the command exceeds *timeout* seconds
        (the process is killed before re-raising).
        """
        ...


class HostRunner:
    """Execute subprocesses on the host using ``asyncio.create_subprocess_exec``."""

    async def create_streaming_process(
        self,
        cmd: Sequence[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        limit: int = 65536,
        start_new_session: bool = False,
    ) -> asyncio.subprocess.Process:
        """Create a streaming subprocess on the host."""
        return await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
            limit=limit,
            start_new_session=start_new_session,
        )

    async def run_simple(
        self,
        cmd: Sequence[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 120.0,
    ) -> SimpleResult:
        """Run a command on the host and return its output.

        Raises ``TimeoutError`` if the command exceeds *timeout* seconds.
        """
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise
        return SimpleResult(
            stdout=stdout.decode().strip(),
            stderr=stderr.decode().strip(),
            returncode=proc.returncode if proc.returncode is not None else -1,
        )


_default_runner: HostRunner | None = None


def get_default_runner() -> HostRunner:
    """Return a module-level ``HostRunner`` singleton."""
    global _default_runner  # noqa: PLW0603
    if _default_runner is None:
        _default_runner = HostRunner()
    return _default_runner
