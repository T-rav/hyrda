"""Tests for ADR file structure and README index consistency."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ADR_DIR = Path(__file__).resolve().parent.parent / "docs" / "adr"
REQUIRED_SECTIONS = ["## Context", "## Decision", "## Consequences"]
STATUS_VALUES = {"Accepted", "Proposed", "Deprecated"}
ADR_FILENAME_RE = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")
README_ROW_RE = re.compile(r"\|\s*\[(\d{4})\]\(([^)]+)\)\s*\|([^|]+)\|([^|]+)\|")


def _adr_files() -> list[Path]:
    """Return all ADR markdown files (excluding README)."""
    return sorted(p for p in ADR_DIR.glob("*.md") if p.name != "README.md")


class TestADRFilenameConventions:
    def test_adr_directory_exists(self) -> None:
        assert ADR_DIR.is_dir(), f"ADR directory not found at {ADR_DIR}"

    def test_adr_files_follow_naming_convention(self) -> None:
        for path in _adr_files():
            assert ADR_FILENAME_RE.match(path.name), (
                f"ADR filename {path.name!r} does not match "
                f"expected pattern NNNN-kebab-case-title.md"
            )

    def test_adr_numbers_are_sequential(self) -> None:
        numbers = [int(p.name[:4]) for p in _adr_files()]
        assert numbers == list(range(1, len(numbers) + 1)), (
            f"ADR numbers are not sequential: {numbers}"
        )


class TestADRContent:
    @pytest.fixture(params=_adr_files(), ids=lambda p: p.name)
    def adr_path(self, request: pytest.FixtureRequest) -> Path:
        return request.param

    def test_has_title_heading(self, adr_path: Path) -> None:
        content = adr_path.read_text()
        assert content.startswith("# ADR-"), (
            f"{adr_path.name} must start with '# ADR-NNNN: <Title>'"
        )

    def test_has_status(self, adr_path: Path) -> None:
        content = adr_path.read_text()
        assert "**Status:**" in content, f"{adr_path.name} missing **Status:** metadata"
        match = re.search(r"\*\*Status:\*\*\s+(\w+)", content)
        assert match, f"{adr_path.name} has malformed Status line"
        status = match.group(1)
        assert status in STATUS_VALUES or status.startswith("Superseded"), (
            f"{adr_path.name} has unexpected status: {status!r}"
        )

    def test_has_date(self, adr_path: Path) -> None:
        content = adr_path.read_text()
        assert "**Date:**" in content, f"{adr_path.name} missing **Date:** metadata"
        assert re.search(r"\*\*Date:\*\*\s+\d{4}-\d{2}-\d{2}", content), (
            f"{adr_path.name} has malformed Date line"
        )

    def test_has_required_sections(self, adr_path: Path) -> None:
        content = adr_path.read_text()
        for section in REQUIRED_SECTIONS:
            assert section in content, (
                f"{adr_path.name} missing required section: {section}"
            )


class TestADRReadmeIndex:
    def test_readme_exists(self) -> None:
        readme = ADR_DIR / "README.md"
        assert readme.exists(), "docs/adr/README.md not found"

    def test_all_adrs_listed_in_readme(self) -> None:
        readme = (ADR_DIR / "README.md").read_text()
        rows = README_ROW_RE.findall(readme)
        indexed_files = {filename for _, filename, _, _ in rows}

        for path in _adr_files():
            assert path.name in indexed_files, (
                f"{path.name} exists on disk but is not listed in README.md index"
            )

    def test_readme_links_point_to_existing_files(self) -> None:
        readme = (ADR_DIR / "README.md").read_text()
        rows = README_ROW_RE.findall(readme)

        for number, filename, _title, _status in rows:
            file_path = ADR_DIR / filename
            assert file_path.exists(), (
                f"README.md references {filename} but file does not exist"
            )
            assert filename.startswith(number), (
                f"README.md row number {number} does not match filename {filename}"
            )

    def test_readme_index_count_matches_files(self) -> None:
        readme = (ADR_DIR / "README.md").read_text()
        rows = README_ROW_RE.findall(readme)
        files = _adr_files()
        assert len(rows) == len(files), (
            f"README.md lists {len(rows)} ADRs but {len(files)} files exist on disk"
        )


class TestADR0009Specifics:
    """Content checks specific to ADR-0009 (persistence architecture)."""

    @pytest.fixture()
    def content(self) -> str:
        path = ADR_DIR / "0009-persistence-architecture-and-data-layout.md"
        assert path.exists(), "ADR-0009 file not found"
        return path.read_text()

    def test_title(self, content: str) -> None:
        assert "# ADR-0009: Persistence Architecture and Data Layout" in content

    def test_status_proposed(self, content: str) -> None:
        assert "**Status:** Proposed" in content

    def test_references_source_memory(self, content: str) -> None:
        assert "#1624" in content, "ADR-0009 must link to source memory issue #1624"

    def test_references_this_issue(self, content: str) -> None:
        assert "#1633" in content, "ADR-0009 must link to this issue #1633"

    def test_documents_data_root(self, content: str) -> None:
        assert "data_root" in content
        assert ".hydraflow" in content

    def test_documents_state_json(self, content: str) -> None:
        assert "state.json" in content

    def test_documents_config_precedence(self, content: str) -> None:
        assert "HYDRAFLOW_HOME" in content
        assert "Pydantic defaults" in content

    def test_documents_atomic_writes(self, content: str) -> None:
        assert "atomic_write" in content

    def test_documents_repo_slug_namespacing(self, content: str) -> None:
        assert "repo_slug" in content or "repo-slug" in content

    def test_has_alternatives_considered(self, content: str) -> None:
        assert "## Alternatives considered" in content

    def test_has_related_section(self, content: str) -> None:
        assert "## Related" in content
