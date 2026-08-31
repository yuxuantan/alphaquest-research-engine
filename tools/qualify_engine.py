from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from alphaquest import __version__ as PACKAGE_VERSION  # noqa: E402
from alphaquest.research.policy import load_research_policy  # noqa: E402
from alphaquest.utils.hashing import file_sha256  # noqa: E402
from alphaquest.version import ENGINE_CONTRACT_VERSION  # noqa: E402


QUALIFICATION_SCHEMA_VERSION = 3
CANONICAL_ENGINE_VALIDATION_COMMAND = "make validate"
CANONICAL_VALIDATION_COMMANDS = (CANONICAL_ENGINE_VALIDATION_COMMAND, "make qualify")
RESEARCH_INVENTORY_PREFLIGHT_COMMAND = "make preflight"


CONTROL_EVIDENCE = (
    {
        "control": "market_data_integrity",
        "evidence": "tests/test_backtest_contracts.py",
        "claim": "Rejects naive/duplicate primary timestamps, invalid OHLC, and non-finite prices.",
    },
    {
        "control": "execution_accounting",
        "evidence": "tests/test_backtest_contracts.py tests/test_backtest_engine.py",
        "claim": "Validates execution assumptions and adverse round-trip cost accounting.",
    },
    {
        "control": "causal_entry_and_exit_ordering",
        "evidence": "tests/test_backtest_engine.py",
        "claim": "Checks next-bar entry, intrabar ordering, pessimistic conflicts, and forced flattening.",
    },
    {
        "control": "deterministic_replay",
        "evidence": "tests/test_golden_reproducibility.py tests/test_backtest_contracts.py",
        "claim": "Pins a golden result signature and verifies input-order normalization.",
    },
    {
        "control": "backtest_execution_parity_contract",
        "evidence": "tests/test_backtest_live_parity.py",
        "claim": "Compares signal identity, timestamp instants, prices, size, and flatten instructions.",
    },
    {
        "control": "staged_research_governance",
        "evidence": "tests/test_campaign_stages.py tests/test_preflight.py tests/test_research_schemas.py",
        "claim": "Fails closed on invalid configs/artifacts and preserves staged promotion gates.",
    },
)

MODEL_LIMITATIONS = (
    "OHLC runs do not model exchange queue position or order-book priority.",
    "SCID record replay is ordered trade-record evidence, not exchange-native MBO sequencing.",
    "Latency, partial fills, market impact, and capacity require venue/broker-specific calibration.",
    "A passing software qualification does not make any strategy tradeable or live-ready.",
    "Historical artifacts created before the current engine contract version must be rerun to inherit it.",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and record the engine software qualification suite.")
    parser.add_argument("--output-dir", default="research_artifacts")
    parser.add_argument("--skip-tests", action="store_true", help="Write metadata only; status becomes NOT_RUN.")
    args = parser.parse_args()

    started = datetime.now(timezone.utc)
    validation_result = _run_validation(skip=args.skip_tests)
    finished = datetime.now(timezone.utc)
    git_commit = _command_output(["git", "rev-parse", "HEAD"])
    output_dir = PROJECT_ROOT / args.output_dir
    dirty_paths = _dirty_paths(output_dir)
    status = _qualification_status(
        skip_tests=args.skip_tests,
        validation_return_code=validation_result["return_code"],
        dirty_paths=dirty_paths,
        python_version=platform.python_version(),
        reference_python_version=_reference_python_version(),
    )
    policy = load_research_policy()
    qualification_reasons = []
    if validation_result["return_code"] not in {0, None}:
        qualification_reasons.append("canonical engine validation surface failed")
    if dirty_paths:
        qualification_reasons.append("worktree is not clean")
    if platform.python_version() != _reference_python_version():
        qualification_reasons.append("qualification did not run under the pinned reference Python")
    report = {
        "qualification_schema_version": QUALIFICATION_SCHEMA_VERSION,
        "engine_software_status": status,
        "qualification_reasons": qualification_reasons,
        "scope": "software verification only; not a candidate-strategy or tradeability verdict",
        "package_version": PACKAGE_VERSION,
        "engine_contract_version": ENGINE_CONTRACT_VERSION,
        "git_commit": git_commit,
        "git_tree": _command_output(["git", "rev-parse", "HEAD^{tree}"]),
        "worktree_dirty": bool(dirty_paths),
        "dirty_paths": dirty_paths,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": (finished - started).total_seconds(),
        "methodology_policy": {
            "version": policy.version,
            "path": str(policy.path.relative_to(PROJECT_ROOT)),
            "sha256": policy.file_hash,
            "implementation_path": "src/alphaquest/research/policy.py",
            "implementation_sha256": file_sha256(PROJECT_ROOT / "src" / "alphaquest" / "research" / "policy.py"),
        },
        "policy_hash": policy.file_hash,
        "engine_hash": file_sha256(PROJECT_ROOT / "src" / "alphaquest" / "backtest" / "engine.py"),
        "contracts_hash": file_sha256(PROJECT_ROOT / "src" / "alphaquest" / "backtest" / "contracts.py"),
        "reference_environment": {
            "python_version": (PROJECT_ROOT / ".python-version").read_text(encoding="utf-8").strip(),
            "node_version": (PROJECT_ROOT / ".nvmrc").read_text(encoding="utf-8").strip(),
            "constraints_path": "constraints/dev.txt",
            "constraints_sha256": file_sha256(PROJECT_ROOT / "constraints" / "dev.txt"),
            "pyproject_sha256": file_sha256(PROJECT_ROOT / "pyproject.toml"),
            "npm_lock_sha256": file_sha256(PROJECT_ROOT / "studio-ui" / "package-lock.json"),
            "ci_workflow_sha256": file_sha256(PROJECT_ROOT / ".github" / "workflows" / "ci.yml"),
            "makefile_sha256": file_sha256(PROJECT_ROOT / "Makefile"),
        },
        "build_identity": {
            "package_source_sha256": _tracked_tree_sha256("src/alphaquest"),
            "studio_web_assets_sha256": _tracked_tree_sha256("src/alphaquest/studio/web_assets"),
        },
        "canonical_validation_commands": list(CANONICAL_VALIDATION_COMMANDS),
        "validation_components": [
            "lint and static checks",
            "documentation validation",
            "smoke tests",
            "methodology regression",
            "causal and execution regression",
            "complete Python surface (tests/ and execution_system/tests/)",
            "Studio UI typecheck and tests",
        ],
        "validation_result": validation_result,
        "research_inventory_preflight": {
            "command": RESEARCH_INVENTORY_PREFLIGHT_COMMAND,
            "included_in_engine_software_status": False,
            "scope": "authored campaign executability; fail-closed and reported separately",
        },
        "control_evidence": list(CONTROL_EVIDENCE),
        "model_limitations": list(MODEL_LIMITATIONS),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "engine_qualification.json"
    markdown_path = output_dir / "engine_qualification.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    display_path = json_path.relative_to(PROJECT_ROOT) if json_path.is_relative_to(PROJECT_ROOT) else json_path
    print(f"{status}: {display_path}")
    return 0 if status in {"PASS", "NOT_RUN"} else 1


def _run_validation(*, skip: bool) -> dict:
    command = ["make", "validate", f"PYTHON={sys.executable}"]
    if skip:
        return {"command": command, "return_code": None, "duration_seconds": 0.0, "output": "not run"}
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": command,
        "return_code": completed.returncode,
        "duration_seconds": time.monotonic() - started,
        "output": completed.stdout[-12000:].strip(),
    }


def _reference_python_version() -> str:
    return (PROJECT_ROOT / ".python-version").read_text(encoding="utf-8").strip()


def _tracked_tree_sha256(path: str) -> str:
    tracked = _command_output(["git", "ls-files", "-z", "--", path]).encode("utf-8")
    digest = hashlib.sha256()
    for relative in sorted(item for item in tracked.split(b"\0") if item):
        relative_path = relative.decode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update((PROJECT_ROOT / relative_path).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _command_output(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.stdout.strip()


def _dirty_paths(output_dir: Path) -> list[str]:
    """Return unexplained changes, excluding this command's replaceable outputs."""

    owned_outputs = {
        (output_dir / "engine_qualification.json").resolve(),
        (output_dir / "engine_qualification.md").resolve(),
    }
    dirty = []
    for line in _command_output(["git", "status", "--short"]).splitlines():
        if not line:
            continue
        raw_path = line[3:].strip()
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        candidate = (PROJECT_ROOT / raw_path.strip('"')).resolve()
        if candidate not in owned_outputs:
            dirty.append(line)
    return dirty


def _qualification_status(
    *,
    skip_tests: bool,
    validation_return_code: int | None,
    dirty_paths: list[str],
    python_version: str,
    reference_python_version: str,
) -> str:
    if skip_tests:
        return "NOT_RUN"
    if validation_return_code == 0 and not dirty_paths and python_version == reference_python_version:
        return "PASS"
    return "FAIL"


def _markdown(report: dict) -> str:
    lines = [
        "# Engine Qualification",
        "",
        f"Software status: **{report['engine_software_status']}**",
        "",
        f"Package version: `{report['package_version']}`",
        f"Engine contract: `{report['engine_contract_version']}`",
        f"Git commit: `{report['git_commit']}`",
        f"Dirty worktree: `{str(report['worktree_dirty']).lower()}`",
        f"Methodology policy: `{report['methodology_policy']['version']}`",
        f"Methodology policy SHA-256: `{report['methodology_policy']['sha256']}`",
        f"Methodology implementation SHA-256: `{report['methodology_policy']['implementation_sha256']}`",
        f"Reference Python: `{report['reference_environment']['python_version']}`",
        f"Reference constraints SHA-256: `{report['reference_environment']['constraints_sha256']}`",
        "",
        "This is a software-verification result. It is not evidence that any candidate strategy is tradeable.",
        "",
        "## Control Evidence",
        "",
    ]
    for item in report["control_evidence"]:
        lines.append(f"- `{item['control']}`: {item['claim']} Evidence: `{item['evidence']}`")
    lines.extend(["", "## Canonical Validation Commands", ""])
    lines.extend(f"- `{item}`" for item in report["canonical_validation_commands"])
    lines.extend(["", "## Model Limitations", ""])
    lines.extend(f"- {item}" for item in report["model_limitations"])
    lines.extend(
        [
            "",
            "## Research Inventory Boundary",
            "",
            f"`{report['research_inventory_preflight']['command']}` is fail-closed research-inventory preflight. ",
            "Its result is reported separately and does not alter the engine software status.",
            "",
            "## Validation Output",
            "",
            "```text",
            report["validation_result"]["output"],
            "```",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
