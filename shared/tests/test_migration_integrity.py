"""Migration integrity tests — verify migration chain and structure.

These tests run in CI without an external database. They validate:
- Every migration has upgrade() and downgrade() functions
- The revision chain is unbroken (no orphans, no gaps)
- Migration files follow naming conventions
- No duplicate revision IDs
"""

import re
from pathlib import Path

import pytest

# Root of the project
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Services with Alembic migrations
MIGRATION_SERVICES = {
    "bot": PROJECT_ROOT / "bot" / "migrations" / "versions",
    "tasks": PROJECT_ROOT / "tasks" / "migrations" / "versions",
    "control_plane": PROJECT_ROOT / "control_plane" / "migrations" / "versions",
}


def _get_migration_files(versions_dir: Path) -> list[Path]:
    """Get all Python migration files in a versions directory."""
    if not versions_dir.exists():
        return []
    return sorted(
        [f for f in versions_dir.glob("*.py") if f.name != "__init__.py"],
        key=lambda f: f.name,
    )


def _extract_revision_info(migration_path: Path) -> "dict | None":
    """Extract revision and down_revision from a migration file via AST/regex.

    Uses regex to avoid import side effects from service-specific dependencies.
    """
    content = migration_path.read_text()

    revision_match = re.search(
        r'^revision\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE
    )
    down_revision_match = re.search(
        r'^down_revision\s*=\s*["\']?([^"\'"\n]+)["\']?', content, re.MULTILINE
    )

    if not revision_match:
        return None

    down_rev = None
    if down_revision_match:
        raw = down_revision_match.group(1).strip()
        if raw.lower() != "none":
            down_rev = raw

    return {
        "revision": revision_match.group(1),
        "down_revision": down_rev,
        "path": migration_path,
    }


class TestMigrationStructure:
    """Test that all migration files have the required structure."""

    @pytest.mark.parametrize("service_name", list(MIGRATION_SERVICES.keys()))
    def test_migrations_directory_exists(self, service_name: str) -> None:
        """Each service has a migrations/versions directory."""
        versions_dir = MIGRATION_SERVICES[service_name]
        assert versions_dir.exists(), (
            f"{service_name} is missing migrations/versions directory at {versions_dir}"
        )

    @pytest.mark.parametrize("service_name", list(MIGRATION_SERVICES.keys()))
    def test_migrations_have_upgrade_and_downgrade(self, service_name: str) -> None:
        """Every migration file must define upgrade() and downgrade() functions."""
        versions_dir = MIGRATION_SERVICES[service_name]
        migration_files = _get_migration_files(versions_dir)

        assert len(migration_files) > 0, f"{service_name} has no migration files"

        for migration_path in migration_files:
            content = migration_path.read_text()

            assert re.search(r"^def upgrade", content, re.MULTILINE), (
                f"{service_name}/{migration_path.name} is missing upgrade() function"
            )
            assert re.search(r"^def downgrade", content, re.MULTILINE), (
                f"{service_name}/{migration_path.name} is missing downgrade() function"
            )

    @pytest.mark.parametrize("service_name", list(MIGRATION_SERVICES.keys()))
    def test_migrations_have_revision_identifiers(self, service_name: str) -> None:
        """Every migration file must have revision and down_revision."""
        versions_dir = MIGRATION_SERVICES[service_name]
        migration_files = _get_migration_files(versions_dir)

        for migration_path in migration_files:
            content = migration_path.read_text()

            assert re.search(r"^revision\s*=", content, re.MULTILINE), (
                f"{service_name}/{migration_path.name} is missing 'revision' identifier"
            )
            assert re.search(r"^down_revision\s*=", content, re.MULTILINE), (
                f"{service_name}/{migration_path.name} is missing 'down_revision' identifier"
            )

    @pytest.mark.parametrize("service_name", list(MIGRATION_SERVICES.keys()))
    def test_migrations_have_docstrings(self, service_name: str) -> None:
        """Every migration file should have a descriptive docstring."""
        versions_dir = MIGRATION_SERVICES[service_name]
        migration_files = _get_migration_files(versions_dir)

        for migration_path in migration_files:
            content = migration_path.read_text()

            assert content.startswith('"""') or content.startswith("'''"), (
                f"{service_name}/{migration_path.name} should start with a docstring "
                f"describing the migration"
            )


class TestMigrationChainIntegrity:
    """Test that the migration chain is unbroken for each service."""

    @pytest.mark.parametrize("service_name", list(MIGRATION_SERVICES.keys()))
    def test_no_duplicate_revisions(self, service_name: str) -> None:
        """No two migrations share the same revision ID."""
        versions_dir = MIGRATION_SERVICES[service_name]
        migration_files = _get_migration_files(versions_dir)

        revisions: dict[str, Path] = {}
        for migration_path in migration_files:
            info = _extract_revision_info(migration_path)
            if info is None:
                continue

            rev = info["revision"]
            assert rev not in revisions, (
                f"{service_name}: Duplicate revision '{rev}' in "
                f"{migration_path.name} and {revisions[rev].name}"
            )
            revisions[rev] = migration_path

    @pytest.mark.parametrize("service_name", list(MIGRATION_SERVICES.keys()))
    def test_exactly_one_root_migration(self, service_name: str) -> None:
        """There should be exactly one migration with down_revision=None (the root)."""
        versions_dir = MIGRATION_SERVICES[service_name]
        migration_files = _get_migration_files(versions_dir)

        roots = []
        for migration_path in migration_files:
            info = _extract_revision_info(migration_path)
            if info and info["down_revision"] is None:
                roots.append(migration_path.name)

        assert len(roots) == 1, (
            f"{service_name}: Expected exactly 1 root migration (down_revision=None), "
            f"found {len(roots)}: {roots}"
        )

    @pytest.mark.parametrize("service_name", list(MIGRATION_SERVICES.keys()))
    def test_chain_is_connected(self, service_name: str) -> None:
        """Every down_revision must point to an existing revision (no orphans)."""
        versions_dir = MIGRATION_SERVICES[service_name]
        migration_files = _get_migration_files(versions_dir)

        all_revisions: set[str] = set()
        migrations_with_deps: list[dict] = []

        for migration_path in migration_files:
            info = _extract_revision_info(migration_path)
            if info is None:
                continue
            all_revisions.add(info["revision"])
            migrations_with_deps.append(info)

        for info in migrations_with_deps:
            down_rev = info["down_revision"]
            if down_rev is not None:
                assert down_rev in all_revisions, (
                    f"{service_name}/{info['path'].name}: "
                    f"down_revision '{down_rev}' does not match any existing revision. "
                    f"Known revisions: {sorted(all_revisions)}"
                )

    @pytest.mark.parametrize("service_name", list(MIGRATION_SERVICES.keys()))
    def test_no_branching(self, service_name: str) -> None:
        """No two migrations should share the same down_revision (no forks)."""
        versions_dir = MIGRATION_SERVICES[service_name]
        migration_files = _get_migration_files(versions_dir)

        down_revisions: dict[str, list[str]] = {}

        for migration_path in migration_files:
            info = _extract_revision_info(migration_path)
            if info is None or info["down_revision"] is None:
                continue

            down_rev = info["down_revision"]
            if down_rev not in down_revisions:
                down_revisions[down_rev] = []
            down_revisions[down_rev].append(migration_path.name)

        for down_rev, files in down_revisions.items():
            assert len(files) == 1, (
                f"{service_name}: Migration branch detected! "
                f"Multiple migrations depend on '{down_rev}': {files}. "
                f"Merge these into a single chain."
            )


class TestMigrationEnvConfiguration:
    """Test that Alembic environment files are properly configured."""

    @pytest.mark.parametrize("service_name", list(MIGRATION_SERVICES.keys()))
    def test_env_py_exists(self, service_name: str) -> None:
        """Each service must have a migrations/env.py."""
        env_path = MIGRATION_SERVICES[service_name].parent / "env.py"
        assert env_path.exists(), f"{service_name} is missing migrations/env.py"

    @pytest.mark.parametrize("service_name", list(MIGRATION_SERVICES.keys()))
    def test_env_py_has_migration_runners(self, service_name: str) -> None:
        """env.py must define run_migrations_offline and run_migrations_online."""
        env_path = MIGRATION_SERVICES[service_name].parent / "env.py"
        if not env_path.exists():
            pytest.skip(f"No env.py for {service_name}")

        content = env_path.read_text()

        assert "run_migrations_offline" in content, (
            f"{service_name}/migrations/env.py is missing run_migrations_offline"
        )
        assert "run_migrations_online" in content, (
            f"{service_name}/migrations/env.py is missing run_migrations_online"
        )
