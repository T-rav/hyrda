from __future__ import annotations

from pathlib import Path

from scripts.bundle_assets import bundle_assets


def test_assets_bundle_is_up_to_date(tmp_path: Path) -> None:
    """Ensure hf_cli/assets.tar.gz stays in sync with the manifest sources."""
    repo_root = Path(__file__).resolve().parents[2]
    generated = tmp_path / "assets.tar.gz"
    bundle_assets(generated, repo_root)
    recorded = repo_root / "hf_cli" / "assets.tar.gz"
    assert generated.read_bytes() == recorded.read_bytes(), (
        "Run `make bundle-assets` after modifying .claude, .codex, or .githooks assets."
    )
