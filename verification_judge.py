"""LLM-as-judge validation of acceptance criteria and verification instructions."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import (
    CriterionResult,
    CriterionVerdict,
    GitHubIssue,
    InstructionsQuality,
    JudgeVerdict,
)
from runner_utils import stream_claude_process, terminate_processes

logger = logging.getLogger("hydra.verification_judge")


class VerificationJudge:
    """Validates acceptance criteria against merged code and evaluates verification instructions.

    Reads criteria from ``.hydra/verification/issue-N.md``, runs LLM evaluations,
    and persists a judge report to ``.hydra/verification/issue-N-judge.md``.
    """

    def __init__(self, config: HydraConfig, event_bus: EventBus) -> None:
        self._config = config
        self._bus = event_bus
        self._active_procs: set[asyncio.subprocess.Process] = set()

    async def judge(
        self,
        issue: GitHubIssue,
        diff: str,
        worker_id: int = 0,
    ) -> JudgeVerdict:
        """Run the verification judge for *issue*.

        Returns a :class:`JudgeVerdict` with per-criterion results and
        instructions quality assessment.
        """
        start = time.monotonic()
        verdict = JudgeVerdict(issue_number=issue.number)

        # Read criteria file — return early if none exists
        criteria_text = self._read_criteria_file(issue.number)
        if criteria_text is None:
            logger.info("No criteria file for issue #%d — skipping judge", issue.number)
            return verdict

        await self._bus.publish(
            HydraEvent(
                type=EventType.VERIFICATION_JUDGE,
                data={
                    "issue": issue.number,
                    "worker": worker_id,
                    "status": "judging",
                },
            )
        )

        if self._config.dry_run:
            logger.info("[dry-run] Would judge issue #%d", issue.number)
            verdict.summary = "Dry-run: judge skipped"
            return verdict

        try:
            # Step 1: Code-level validation
            cmd = self._build_command()
            code_prompt = self._build_code_validation_prompt(issue, diff, criteria_text)
            code_transcript = await self._execute(cmd, code_prompt, issue.number)
            verdict.criteria_results = self._parse_criteria_results(code_transcript)
            verdict.all_criteria_pass = (
                all(
                    c.verdict == CriterionVerdict.PASS for c in verdict.criteria_results
                )
                and len(verdict.criteria_results) > 0
            )

            # Step 2: Instructions validation
            instructions_prompt = self._build_instructions_validation_prompt(
                issue, criteria_text
            )
            instructions_transcript = await self._execute(
                cmd, instructions_prompt, issue.number
            )
            quality, feedback = self._parse_instructions_quality(
                instructions_transcript
            )
            verdict.instructions_quality = quality
            verdict.instructions_feedback = feedback

            # Step 3: Auto-refine if needed (max 1 retry)
            if quality == InstructionsQuality.NEEDS_REFINEMENT:
                refinement_prompt = self._build_refinement_prompt(
                    issue, criteria_text, feedback
                )
                refinement_transcript = await self._execute(
                    cmd, refinement_prompt, issue.number
                )
                refined_text = self._extract_refined_instructions(refinement_transcript)
                if refined_text:
                    self._update_criteria_file(issue.number, refined_text)
                    verdict.refined = True

                    # Re-validate refined instructions
                    updated_criteria = self._read_criteria_file(issue.number)
                    if updated_criteria:
                        revalidation_transcript = await self._execute(
                            cmd,
                            self._build_instructions_validation_prompt(
                                issue, updated_criteria
                            ),
                            issue.number,
                        )
                        new_quality, new_feedback = self._parse_instructions_quality(
                            revalidation_transcript
                        )
                        verdict.instructions_quality = new_quality
                        verdict.instructions_feedback = new_feedback

            verdict.transcript = code_transcript
            verdict.summary = self._build_summary(verdict)

        except Exception as exc:
            verdict.summary = f"Judge failed: {exc}"
            logger.error("Judge failed for issue #%d: %s", issue.number, exc)

        # Save report and publish done event
        self._save_judge_report(issue.number, verdict)

        await self._bus.publish(
            HydraEvent(
                type=EventType.VERIFICATION_JUDGE,
                data={
                    "issue": issue.number,
                    "worker": worker_id,
                    "status": "done",
                    "all_pass": verdict.all_criteria_pass,
                    "instructions_quality": verdict.instructions_quality.value,
                    "duration": time.monotonic() - start,
                },
            )
        )

        return verdict

    def _read_criteria_file(self, issue_number: int) -> str | None:
        """Read the criteria file for the given issue number."""
        path = (
            self._config.repo_root
            / ".hydra"
            / "verification"
            / f"issue-{issue_number}.md"
        )
        if not path.exists():
            return None
        return path.read_text()

    def _build_command(self) -> list[str]:
        """Construct the ``claude`` CLI invocation for the judge.

        Uses read-only mode (disallowed write tools) since the judge
        only evaluates code, not modifies it.
        """
        cmd = [
            "claude",
            "-p",
            "--output-format",
            "stream-json",
            "--model",
            self._config.review_model,
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
            "--disallowedTools",
            "Write,Edit,NotebookEdit",
        ]
        if self._config.review_budget_usd > 0:
            cmd.extend(["--max-budget-usd", str(self._config.review_budget_usd)])
        return cmd

    def _build_code_validation_prompt(
        self, issue: GitHubIssue, diff: str, criteria_text: str
    ) -> str:
        """Build the prompt for evaluating acceptance criteria against the diff."""
        return f"""You are a verification judge evaluating whether the merged code for issue #{issue.number} meets its acceptance criteria.

## Issue: {issue.title}

{issue.body}

## Acceptance Criteria

{criteria_text}

## Merged Diff

```diff
{diff[:15000]}
```

## Instructions

Evaluate EACH acceptance criterion against the merged diff and test coverage. For each criterion, determine if it is met (PASS) or not met (FAIL).

## Required Output

Output your evaluation between these markers:

CRITERIA_START
AC-1: PASS — <reasoning and evidence>
AC-2: FAIL — <reasoning for failure>
CRITERIA_END

SUMMARY: <overall summary of criteria evaluation>

Rules:
- Use EXACTLY the format "AC-N: PASS — reasoning" or "AC-N: FAIL — reasoning"
- Evaluate EVERY criterion listed above
- Be specific about evidence (test files, code locations, etc.)
"""

    def _build_instructions_validation_prompt(
        self, issue: GitHubIssue, criteria_text: str
    ) -> str:
        """Build the prompt for evaluating verification instructions quality."""
        return f"""You are evaluating the quality of human verification instructions for issue #{issue.number} ({issue.title}).

## Criteria and Instructions

{criteria_text}

## Evaluation Criteria

Evaluate the human verification instructions for:
1. **Specificity**: Are steps specific enough to follow without guessing?
2. **References**: Do steps reference actual UI elements, endpoints, or commands?
3. **Expected outcomes**: Are expected outcomes clearly stated for each step?
4. **Completeness**: Is anything ambiguous or missing?
5. **Actionable**: Can a human follow these steps without additional context?

## Required Output

QUALITY: READY or NEEDS_REFINEMENT
FEEDBACK: <specific feedback about the instructions quality>

Rules:
- Output EXACTLY "QUALITY: READY" if instructions are clear and actionable
- Output EXACTLY "QUALITY: NEEDS_REFINEMENT" if instructions need improvement
- FEEDBACK must explain what is good or what needs fixing
"""

    def _build_refinement_prompt(
        self, issue: GitHubIssue, criteria_text: str, feedback: str
    ) -> str:
        """Build the prompt for refining unclear instructions."""
        return f"""You are refining the human verification instructions for issue #{issue.number} ({issue.title}).

## Original Criteria and Instructions

{criteria_text}

## Feedback on Current Instructions

{feedback}

## Task

Rewrite the verification instructions to address the feedback. Make them:
- Specific and actionable
- Reference actual UI elements, endpoints, or commands
- Include clear expected outcomes for each step
- Remove any ambiguity

## Required Output

Output the refined instructions between these markers:

REFINED_INSTRUCTIONS_START
<your refined step-by-step instructions here>
REFINED_INSTRUCTIONS_END
"""

    def _parse_criteria_results(self, transcript: str) -> list[CriterionResult]:
        """Parse per-criterion PASS/FAIL results from the transcript."""
        # Extract the block between markers
        block_match = re.search(
            r"CRITERIA_START\s*\n(.*?)CRITERIA_END",
            transcript,
            re.DOTALL | re.IGNORECASE,
        )
        if not block_match:
            return []

        block = block_match.group(1)
        results: list[CriterionResult] = []
        pattern = r"(AC-\d+):\s*(PASS|FAIL)\s*[—\-]\s*(.*)"

        for match in re.finditer(pattern, block, re.IGNORECASE):
            criterion_id = match.group(1).upper()
            verdict_str = match.group(2).upper()
            reasoning = match.group(3).strip()

            verdict = (
                CriterionVerdict.PASS
                if verdict_str == "PASS"
                else CriterionVerdict.FAIL
            )
            results.append(
                CriterionResult(
                    criterion_id=criterion_id,
                    verdict=verdict,
                    reasoning=reasoning,
                )
            )

        return results

    def _parse_instructions_quality(
        self, transcript: str
    ) -> tuple[InstructionsQuality, str]:
        """Parse the instructions quality verdict from the transcript."""
        quality_match = re.search(
            r"QUALITY:\s*(READY|NEEDS_REFINEMENT)", transcript, re.IGNORECASE
        )
        feedback_match = re.search(r"FEEDBACK:\s*(.+)", transcript, re.IGNORECASE)

        if quality_match:
            raw = quality_match.group(1).upper()
            quality = (
                InstructionsQuality.READY
                if raw == "READY"
                else InstructionsQuality.NEEDS_REFINEMENT
            )
        else:
            quality = InstructionsQuality.NEEDS_REFINEMENT

        feedback = feedback_match.group(1).strip() if feedback_match else ""
        return quality, feedback

    def _extract_refined_instructions(self, transcript: str) -> str:
        """Extract refined instructions from between markers."""
        match = re.search(
            r"REFINED_INSTRUCTIONS_START\s*\n(.*?)REFINED_INSTRUCTIONS_END",
            transcript,
            re.DOTALL | re.IGNORECASE,
        )
        if not match:
            return ""
        return match.group(1).strip()

    def _save_judge_report(self, issue_number: int, verdict: JudgeVerdict) -> None:
        """Write the judge report to .hydra/verification/issue-N-judge.md."""
        report_dir = self._config.repo_root / ".hydra" / "verification"
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f"issue-{issue_number}-judge.md"

        lines = [
            f"# Verification Judge Report — Issue #{issue_number}\n",
            "",
            "## Criteria Evaluation\n",
            "",
        ]

        if verdict.criteria_results:
            lines.append("| Criterion | Verdict | Reasoning |")
            lines.append("|-----------|---------|-----------|")
            for cr in verdict.criteria_results:
                lines.append(
                    f"| {cr.criterion_id} | {cr.verdict.value.upper()} "
                    f"| {cr.reasoning} |"
                )
            lines.append("")
            pass_count = sum(
                1
                for c in verdict.criteria_results
                if c.verdict == CriterionVerdict.PASS
            )
            total = len(verdict.criteria_results)
            lines.append(f"**Result:** {pass_count}/{total} criteria passed\n")
        else:
            lines.append("No criteria evaluated.\n")

        lines.append("")
        lines.append("## Instructions Quality\n")
        lines.append("")
        lines.append(f"**Quality:** {verdict.instructions_quality.value}\n")
        if verdict.instructions_feedback:
            lines.append(f"**Feedback:** {verdict.instructions_feedback}\n")
        if verdict.refined:
            lines.append(
                "**Note:** Instructions were refined during this evaluation.\n"
            )

        lines.append("")
        lines.append("## Summary\n")
        lines.append("")
        lines.append(f"{verdict.summary}\n")

        path.write_text("\n".join(lines))
        logger.info("Judge report saved to %s", path, extra={"issue": issue_number})

    def _update_criteria_file(
        self, issue_number: int, refined_instructions: str
    ) -> None:
        """Replace the instructions section in the criteria file with refined version."""
        path = (
            self._config.repo_root
            / ".hydra"
            / "verification"
            / f"issue-{issue_number}.md"
        )
        if not path.exists():
            return

        content = path.read_text()

        # Try to replace the existing instructions section
        pattern = r"(## Verification Instructions\s*\n).*"
        replacement = f"\\1\n{refined_instructions}\n"
        new_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)

        if count == 0:
            # No instructions section found — append one
            new_content = (
                content.rstrip()
                + "\n\n## Verification Instructions\n\n"
                + refined_instructions
                + "\n"
            )

        path.write_text(new_content)

    def _build_summary(self, verdict: JudgeVerdict) -> str:
        """Build a human-readable summary from the verdict."""
        parts: list[str] = []
        if verdict.criteria_results:
            pass_count = sum(
                1
                for c in verdict.criteria_results
                if c.verdict == CriterionVerdict.PASS
            )
            total = len(verdict.criteria_results)
            parts.append(f"{pass_count}/{total} criteria passed")
        parts.append(f"instructions: {verdict.instructions_quality.value}")
        if verdict.refined:
            parts.append("(refined)")
        return "; ".join(parts)

    async def _execute(self, cmd: list[str], prompt: str, issue_number: int) -> str:
        """Run the claude judge process."""
        return await stream_claude_process(
            cmd=cmd,
            prompt=prompt,
            cwd=self._config.repo_root,
            active_procs=self._active_procs,
            event_bus=self._bus,
            event_data={"issue": issue_number, "source": "verification_judge"},
            logger=logger,
        )

    def terminate(self) -> None:
        """Kill all active judge subprocesses."""
        terminate_processes(self._active_procs)
