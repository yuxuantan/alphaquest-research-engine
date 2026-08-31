from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = PROJECT_ROOT / "tools" / "qualify_engine.py"
SPEC = importlib.util.spec_from_file_location("qualify_engine", TOOL_PATH)
qualify_engine = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(qualify_engine)


def test_qualification_requires_tests_and_clean_worktree() -> None:
    assert qualify_engine._qualification_status(
        skip_tests=False,
        validation_return_code=0,
        dirty_paths=[],
        python_version="3.12.14",
        reference_python_version="3.12.14",
    ) == "PASS"
    assert qualify_engine._qualification_status(
        skip_tests=False,
        validation_return_code=1,
        dirty_paths=[],
        python_version="3.12.14",
        reference_python_version="3.12.14",
    ) == "FAIL"
    assert qualify_engine._qualification_status(
        skip_tests=False,
        validation_return_code=0,
        dirty_paths=[" M pyproject.toml"],
        python_version="3.12.14",
        reference_python_version="3.12.14",
    ) == "FAIL"
    assert qualify_engine._qualification_status(
        skip_tests=True,
        validation_return_code=None,
        dirty_paths=[" M pyproject.toml"],
        python_version="3.12.5",
        reference_python_version="3.12.14",
    ) == "NOT_RUN"
    assert qualify_engine._qualification_status(
        skip_tests=False,
        validation_return_code=0,
        dirty_paths=[],
        python_version="3.12.5",
        reference_python_version="3.12.14",
    ) == "FAIL"


def test_qualification_report_binds_methodology_environment_and_commands(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "--skip-tests",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads((tmp_path / "engine_qualification.json").read_text(encoding="utf-8"))
    assert report["qualification_schema_version"] == 3
    assert report["engine_software_status"] == "NOT_RUN"
    assert "qualified_for_release" not in report
    assert report["package_version"] == "0.1.0"
    assert report["methodology_policy"]["version"] == "2026-08-14.2"
    assert len(report["methodology_policy"]["sha256"]) == 64
    assert len(report["methodology_policy"]["implementation_sha256"]) == 64
    assert report["reference_environment"]["python_version"] == "3.12.14"
    assert report["reference_environment"]["node_version"] == "22.8.0"
    assert len(report["reference_environment"]["constraints_sha256"]) == 64
    assert "make validate" in report["canonical_validation_commands"]
    assert "make preflight" not in report["canonical_validation_commands"]
    assert report["research_inventory_preflight"] == {
        "command": "make preflight",
        "included_in_engine_software_status": False,
        "scope": "authored campaign executability; fail-closed and reported separately",
    }
    assert report["validation_result"]["output"] == "not run"
    assert report["validation_result"]["command"] == [
        "make",
        "validate",
        f"PYTHON={sys.executable}",
    ]
    assert len(report["build_identity"]["package_source_sha256"]) == 64


def test_canonical_engine_validation_covers_all_hermetic_categories_without_research_preflight() -> None:
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
    validate_line = next(line for line in makefile.splitlines() if line.startswith("validate:"))

    assert validate_line.split()[1:] == [
        "lint",
        "docs-check",
        "smoke",
        "methodology-regression",
        "causal-execution-regression",
        "test",
        "studio-ui-check",
    ]
    assert "preflight" not in validate_line
    assert qualify_engine.CANONICAL_ENGINE_VALIDATION_COMMAND == "make validate"
    assert qualify_engine.RESEARCH_INVENTORY_PREFLIGHT_COMMAND == "make preflight"
