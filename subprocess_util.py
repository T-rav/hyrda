"""Shared async subprocess helper for Hydra."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path


async def run_subprocess(
    *cmd: str,
    cwd: Path | None = None,
    gh_token: str = "",
) -> str:
    """Run a subprocess and return stripped stdout.

    Strips the ``CLAUDECODE`` key from the environment to prevent
    nesting detection.  When *gh_token* is non-empty it is injected
    as ``GH_TOKEN``.

    Raises :class:`RuntimeError` on non-zero exit.
    """
    env = {**os.environ}
    env.pop("CLAUDECODE", None)
    if gh_token:
        env["GH_TOKEN"] = gh_token

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command {cmd!r} failed (rc={proc.returncode}): {stderr.decode().strip()}"
        )
    return stdout.decode().strip()
