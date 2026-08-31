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
        test_return_code=0,
        dirty_paths=[],
    ) == "PASS"
    assert qualify_engine._qualification_status(
        skip_tests=False,
        test_return_code=1,
        dirty_paths=[],
    ) == "FAIL"
    assert qualify_engine._qualification_status(
        skip_tests=False,
        test_return_code=0,
        dirty_paths=[" M pyproject.toml"],
    ) == "FAIL"
    assert qualify_engine._qualification_status(
        skip_tests=True,
        test_return_code=None,
        dirty_paths=[" M pyproject.toml"],
    ) == "NOT_RUN"


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
    assert report["qualification_schema_version"] == 2
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
    assert "make preflight" in report["canonical_validation_commands"]
