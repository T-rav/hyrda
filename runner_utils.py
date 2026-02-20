"""Shared subprocess streaming utilities for Claude agent runners."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from events import EventBus, EventType, HydraEvent
from stream_parser import StreamParser
from subprocess_util import make_clean_env


async def stream_claude_process(
    *,
    cmd: list[str],
    prompt: str,
    cwd: Path,
    active_procs: set[asyncio.subprocess.Process],
    event_bus: EventBus,
    event_data: dict[str, Any],
    logger: logging.Logger,
    on_output: Callable[[str], bool] | None = None,
) -> str:
    """Run a ``claude -p`` subprocess and stream its output.

    Parameters
    ----------
    cmd:
        Command to execute (e.g. ``["claude", "-p", ...]``).
    prompt:
        Text to write to the process's stdin.
    cwd:
        Working directory for the subprocess.
    active_procs:
        Shared set for tracking active processes (for terminate).
    event_bus:
        For publishing ``TRANSCRIPT_LINE`` events.
    event_data:
        Base dict for event data (runner-specific keys like ``issue``/``pr``/``source``).
        ``"line"`` is added automatically per output line.
    logger:
        Caller's logger for warnings (preserves per-runner log context).
    on_output:
        Optional callback receiving accumulated display text.
        Return ``True`` to kill the process early.

    Returns
    -------
    str
        The transcript string, using the fallback chain:
        result_text → accumulated_text → raw_lines.
    """
    env = make_clean_env()

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
        env=env,
        limit=1024 * 1024,  # 1 MB — stream-json lines can exceed 64 KB default
    )
    active_procs.add(proc)

    try:
        assert proc.stdin is not None
        assert proc.stdout is not None
        assert proc.stderr is not None

        proc.stdin.write(prompt.encode())
        await proc.stdin.drain()
        proc.stdin.close()

        # Drain stderr in background to prevent deadlock
        stderr_task = asyncio.create_task(proc.stderr.read())

        parser = StreamParser()
        raw_lines: list[str] = []
        result_text = ""
        accumulated_text = ""
        early_killed = False

        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip("\n")
            raw_lines.append(line)
            if not line.strip():
                continue

            display, result = parser.parse(line)
            if result is not None:
                result_text = result

            if display.strip():
                accumulated_text += display + "\n"
                await event_bus.publish(
                    HydraEvent(
                        type=EventType.TRANSCRIPT_LINE,
                        data={**event_data, "line": display},
                    )
                )

            if (
                on_output is not None
                and not early_killed
                and on_output(accumulated_text)
            ):
                early_killed = True
                proc.kill()
                break

        stderr_bytes = await stderr_task
        await proc.wait()

        if not early_killed and proc.returncode != 0:
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            logger.warning(
                "Process exited with code %d: %s",
                proc.returncode,
                stderr_text[:500],
            )

        return result_text or accumulated_text.rstrip("\n") or "\n".join(raw_lines)
    except asyncio.CancelledError:
        proc.kill()
        raise
    finally:
        active_procs.discard(proc)


def terminate_processes(active_procs: set[asyncio.subprocess.Process]) -> None:
    """Kill all processes in *active_procs*, ignoring already-exited ones."""
    for proc in list(active_procs):
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
