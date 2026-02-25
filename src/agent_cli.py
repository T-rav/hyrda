"""Agent CLI command builders for Claude, Codex, and Pi backends."""

from __future__ import annotations

from typing import Literal

AgentTool = Literal["claude", "codex", "pi"]


def build_agent_command(
    *,
    tool: AgentTool,
    model: str,
    disallowed_tools: str | None = None,
    max_turns: int | None = None,
) -> list[str]:
    """Build a non-interactive command for an agent stage."""
    if tool == "codex":
        return _build_codex_command(model=model)
    if tool == "pi":
        return _build_pi_command(model=model, max_turns=max_turns)

    cmd = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--model",
        model,
        "--verbose",
        "--permission-mode",
        "bypassPermissions",
    ]
    if disallowed_tools:
        cmd.extend(["--disallowedTools", disallowed_tools])
    if max_turns is not None:
        cmd.extend(["--max-turns", str(max_turns)])
    return cmd


def _build_codex_command(*, model: str) -> list[str]:
    """Build a Codex `exec` command with non-interactive automation settings."""
    return [
        "codex",
        "exec",
        "--json",
        "--model",
        model,
        "--sandbox",
        "danger-full-access",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
    ]


def _build_pi_command(*, model: str, max_turns: int | None = None) -> list[str]:
    """Build a Pi headless command that emits machine-readable output."""
    cmd = [
        "pi",
        "-p",
        "--mode",
        "json",
        "--model",
        model,
    ]
    # Pi has no native max-turns flag; add explicit stop guidance instead.
    if max_turns is not None:
        cmd.extend(
            [
                "--append-system-prompt",
                (
                    "Limit yourself to at most "
                    f"{max_turns} assistant turn(s) and then stop."
                ),
            ]
        )
    return cmd
