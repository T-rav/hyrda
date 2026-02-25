"""Contract test: every non-hf_cli src module must have direct unit coverage."""

from __future__ import annotations

import ast
from pathlib import Path


def _has_test_callable(test_file: Path) -> bool:
    tree = ast.parse(test_file.read_text())
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and node.name.startswith("test_"):
            return True
    return False


def test_non_hf_cli_modules_have_direct_tests() -> None:
    src_modules = sorted(
        p
        for p in Path("src").glob("*.py")
        if p.name not in {"__init__.py", "__main__.py"}
    )
    missing_files: list[str] = []
    no_test_callables: list[str] = []

    for module in src_modules:
        test_file = Path("tests") / f"test_{module.stem}.py"
        if not test_file.exists():
            missing_files.append(module.name)
            continue
        if not _has_test_callable(test_file):
            no_test_callables.append(test_file.name)

    assert not missing_files, "Missing direct test files for src modules: " + ", ".join(
        missing_files
    )
    assert not no_test_callables, (
        "Test files exist but define no test_ callables: "
        + ", ".join(no_test_callables)
    )
