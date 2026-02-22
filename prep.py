"""Repository preparation — create Hydra lifecycle labels."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from config import HydraConfig
from subprocess_util import run_subprocess_with_retry

logger = logging.getLogger("hydra.prep")

# Authoritative Hydra lifecycle label table: (config_field, color, description)
HYDRA_LABELS: tuple[tuple[str, str, str], ...] = (
    ("find_label", "e4e669", "New issue for Hydra to discover and triage"),
    ("planner_label", "c5def5", "Issue needs planning before implementation"),
    ("ready_label", "0e8a16", "Issue ready for implementation"),
    ("review_label", "fbca04", "Issue/PR under review"),
    ("hitl_label", "d93f0b", "Escalated to human-in-the-loop"),
    ("hitl_active_label", "e99695", "Being processed by HITL correction agent"),
    ("fixed_label", "0075ca", "PR merged — issue completed"),
    ("improve_label", "7057ff", "Review insight improvement proposal"),
    ("memory_label", "1d76db", "Approved memory suggestion for sync"),
    ("metrics_label", "006b75", "Metrics persistence issue"),
    ("dup_label", "cfd3d7", "Issue already satisfied — no changes needed"),
    ("epic_label", "5319e7", "Epic tracking issue with linked sub-issues"),
)


@dataclass
class PrepResult:
    """Outcome of a label-preparation run."""

    created: list[str] = field(default_factory=list)
    existed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary line."""
        parts = [
            f"Created {len(self.created)} labels, {len(self.existed)} already existed"
        ]
        if self.failed:
            parts.append(f", {len(self.failed)} failed")
        return "".join(parts)


async def _list_existing_labels(config: HydraConfig) -> set[str]:
    """Query the repo for existing label names."""
    try:
        raw = await run_subprocess_with_retry(
            "gh",
            "label",
            "list",
            "--repo",
            config.repo,
            "--json",
            "name",
            "--limit",
            "200",
            cwd=config.repo_root,
            gh_token=config.gh_token,
            max_retries=config.gh_max_retries,
        )
        return {entry["name"] for entry in json.loads(raw)}
    except (RuntimeError, json.JSONDecodeError, KeyError) as exc:
        logger.warning("Could not list existing labels: %s", exc)
        return set()


async def ensure_labels(config: HydraConfig) -> PrepResult:
    """Create all Hydra lifecycle labels on the target repo.

    Uses ``gh label create --force`` which creates or updates each label.
    Returns a :class:`PrepResult` with created/existed/failed lists.
    """
    result = PrepResult()

    if config.dry_run:
        for cfg_field, _color, _desc in HYDRA_LABELS:
            for name in getattr(config, cfg_field):
                result.created.append(name)
        logger.info("[dry-run] Would create labels: %s", result.created)
        return result

    existing = await _list_existing_labels(config)

    for cfg_field, color, description in HYDRA_LABELS:
        label_names: list[str] = getattr(config, cfg_field)
        for label_name in label_names:
            try:
                await run_subprocess_with_retry(
                    "gh",
                    "label",
                    "create",
                    label_name,
                    "--repo",
                    config.repo,
                    "--color",
                    color,
                    "--description",
                    description,
                    "--force",
                    cwd=config.repo_root,
                    gh_token=config.gh_token,
                    max_retries=config.gh_max_retries,
                )
                if label_name in existing:
                    result.existed.append(label_name)
                    logger.debug("Label %r already existed (updated)", label_name)
                else:
                    result.created.append(label_name)
                    logger.info("Created label %r", label_name)
            except RuntimeError as exc:
                result.failed.append(label_name)
                logger.warning("Could not create label %r: %s", label_name, exc)

    return result
