from __future__ import annotations

import argparse
from datetime import datetime, timezone
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


QUALIFICATION_SCHEMA_VERSION = 2
METHODOLOGY_REGRESSION_COMMAND = (
    "python -m pytest -q tests/test_research_policy.py tests/test_research_governance.py "
    "tests/test_campaign_stages.py tests/test_wfa.py tests/test_monte_carlo.py "
    "tests/test_research_execution.py tests/test_run_store.py tests/test_experiment_registry.py "
    "tests/test_strategy_certification.py tests/test_execution_certification.py "
    "tests/test_validation_promotion_gate.py tests/test_data_source_hash.py"
)
CAUSAL_EXECUTION_REGRESSION_COMMAND = (
    "python -m pytest -q tests/test_backtest_contracts.py tests/test_backtest_engine.py "
    "tests/test_order_simulation.py tests/test_sessions.py tests/test_event_replay.py "
    "tests/test_event_replay_partial_exit.py tests/test_position_sizing.py "
    "tests/test_backtest_live_parity.py tests/test_forward_reconciliation.py "
    "tests/test_studio_execution_contract.py"
)
CANONICAL_VALIDATION_COMMANDS = (
    "make smoke",
    METHODOLOGY_REGRESSION_COMMAND,
    CAUSAL_EXECUTION_REGRESSION_COMMAND,
    "make validate",
    "make preflight",
    "make qualify",
)


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
    test_result = _run_tests(skip=args.skip_tests)
    finished = datetime.now(timezone.utc)
    git_commit = _command_output(["git", "rev-parse", "HEAD"])
    output_dir = PROJECT_ROOT / args.output_dir
    dirty_paths = _dirty_paths(output_dir)
    status = _qualification_status(
        skip_tests=args.skip_tests,
        test_return_code=test_result["return_code"],
        dirty_paths=dirty_paths,
    )
    policy = load_research_policy()
    qualification_reasons = []
    if test_result["return_code"] not in {0, None}:
        qualification_reasons.append("canonical Python test surface failed")
    if dirty_paths:
        qualification_reasons.append("worktree is not clean")
    report = {
        "qualification_schema_version": QUALIFICATION_SCHEMA_VERSION,
        "engine_software_status": status,
        "qualification_reasons": qualification_reasons,
        "scope": "software verification only; not a candidate-strategy or tradeability verdict",
        "package_version": PACKAGE_VERSION,
        "engine_contract_version": ENGINE_CONTRACT_VERSION,
        "git_commit": git_commit,
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
        },
        "canonical_validation_commands": list(CANONICAL_VALIDATION_COMMANDS),
        "test_result": test_result,
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


def _run_tests(*, skip: bool) -> dict:
    command = [sys.executable, "-m", "pytest", "-q"]
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


def _qualification_status(*, skip_tests: bool, test_return_code: int | None, dirty_paths: list[str]) -> str:
    if skip_tests:
        return "NOT_RUN"
    if test_return_code == 0 and not dirty_paths:
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
    lines.extend(["", "## Test Output", "", "```text", report["test_result"]["output"], "```", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
