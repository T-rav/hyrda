"""Automated transcript summarization for agent phases."""

from __future__ import annotations

import asyncio
import logging

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from pr_manager import PRManager
from state import StateTracker
from subprocess_util import make_clean_env

logger = logging.getLogger("hydra.transcript_summarizer")

_MIN_TRANSCRIPT_LENGTH = 500


def build_transcript_summary_body(
    issue_number: int,
    phase: str,
    summary_content: str,
    issue_title: str = "",
    duration_seconds: float = 0.0,
) -> str:
    """Format a structured GitHub issue body for a transcript summary."""
    lines = ["## Transcript Summary\n"]
    if issue_title:
        lines.append(f"**Issue:** #{issue_number} — {issue_title}")
    else:
        lines.append(f"**Issue:** #{issue_number}")
    lines.append(f"**Phase:** {phase}")
    if duration_seconds > 0:
        lines.append(f"**Duration:** {duration_seconds:.0f}s")
    lines.append("")
    lines.append(summary_content)
    lines.append("")
    lines.append("---")
    lines.append(
        f"*Auto-generated from transcript of issue #{issue_number} ({phase} phase)*"
    )
    return "\n".join(lines)


def _truncate_transcript(transcript: str, max_chars: int) -> str:
    """Cap transcript size, keeping the end (most useful decisions/errors)."""
    if len(transcript) <= max_chars:
        return transcript
    marker = "...(transcript truncated)...\n\n"
    return marker + transcript[-(max_chars - len(marker)) :]


_SUMMARIZATION_PROMPT = """\
You are analysing an agent transcript from a software engineering pipeline.
Extract a structured summary with ONLY the sections that have content.
Use these section headings (omit any section with nothing to report):

### Key Decisions
### Patterns Discovered
### Errors Encountered
### Workarounds Applied
### Codebase Insights

Each section should contain concise bullet points.
Do NOT include preamble or closing remarks — output ONLY the markdown sections.

--- TRANSCRIPT ---
{transcript}
"""


class TranscriptSummarizer:
    """Summarizes agent transcripts and publishes them as GitHub issues."""

    def __init__(
        self,
        config: HydraConfig,
        pr_manager: PRManager,
        event_bus: EventBus,
        state: StateTracker,
    ) -> None:
        self._config = config
        self._prs = pr_manager
        self._bus = event_bus
        self._state = state

    async def summarize_and_publish(
        self,
        transcript: str,
        issue_number: int,
        phase: str,
        issue_title: str = "",
        duration_seconds: float = 0.0,
    ) -> int | None:
        """Summarize a transcript and publish as a GitHub issue.

        Returns the created issue number, or ``None`` if skipped/failed.
        Never raises — all errors are logged and swallowed.
        """
        try:
            return await self._summarize_and_publish_inner(
                transcript, issue_number, phase, issue_title, duration_seconds
            )
        except Exception:
            logger.exception(
                "Transcript summarization failed for issue #%d (%s phase)",
                issue_number,
                phase,
            )
            return None

    async def _summarize_and_publish_inner(
        self,
        transcript: str,
        issue_number: int,
        phase: str,
        issue_title: str,
        duration_seconds: float,
    ) -> int | None:
        """Inner implementation — may raise."""
        if not self._config.transcript_summarization_enabled:
            return None

        if not transcript or not transcript.strip():
            return None

        if len(transcript.strip()) < _MIN_TRANSCRIPT_LENGTH:
            return None

        # Truncate if needed (keep the end)
        truncated = _truncate_transcript(
            transcript, self._config.max_transcript_summary_chars
        )

        # Build prompt and call model
        prompt = _SUMMARIZATION_PROMPT.format(transcript=truncated)
        summary_content = await self._call_model(prompt)
        if not summary_content:
            return None

        # Build issue body
        body = build_transcript_summary_body(
            issue_number=issue_number,
            phase=phase,
            summary_content=summary_content,
            issue_title=issue_title,
            duration_seconds=duration_seconds,
        )

        title = f"[Transcript Summary] Issue #{issue_number} — {phase} phase"
        labels = list(self._config.improve_label) + list(self._config.hitl_label)

        issue_num = await self._prs.create_issue(title, body, labels)
        if issue_num:
            self._state.set_hitl_origin(issue_num, self._config.improve_label[0])
            self._state.set_hitl_cause(issue_num, "Transcript summary")
            await self._bus.publish(
                HydraEvent(
                    type=EventType.TRANSCRIPT_SUMMARY,
                    data={
                        "source_issue": issue_number,
                        "phase": phase,
                        "summary_issue": issue_num,
                    },
                )
            )
            logger.info(
                "Filed transcript summary as issue #%d for issue #%d (%s phase)",
                issue_num,
                issue_number,
                phase,
            )
            return issue_num

        return None

    async def _call_model(self, prompt: str) -> str | None:
        """Call the Claude CLI to summarize.

        Returns the model output, or ``None`` on failure.
        """
        model = self._config.transcript_summary_model
        cmd = ["claude", "-p", "--model", model]
        env = make_clean_env(self._config.gh_token)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()), timeout=120
            )
            if proc.returncode != 0:
                logger.warning(
                    "Transcript summary model failed (rc=%d): %s",
                    proc.returncode,
                    stderr.decode().strip()[:200],
                )
                return None
            result = stdout.decode().strip()
            return result if result else None
        except TimeoutError:
            logger.warning("Transcript summary model timed out")
            return None
        except (OSError, FileNotFoundError) as exc:
            logger.warning("Transcript summary model unavailable: %s", exc)
            return None
