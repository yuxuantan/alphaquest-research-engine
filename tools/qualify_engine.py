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

from propstack.utils.hashing import file_sha256  # noqa: E402
from propstack.version import ENGINE_CONTRACT_VERSION  # noqa: E402


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
    dirty_paths = [line for line in _command_output(["git", "status", "--short"]).splitlines() if line]
    status = "NOT_RUN" if args.skip_tests else "PASS" if test_result["return_code"] == 0 else "FAIL"
    report = {
        "engine_software_status": status,
        "scope": "software verification only; not a candidate-strategy or tradeability verdict",
        "engine_contract_version": ENGINE_CONTRACT_VERSION,
        "git_commit": git_commit,
        "worktree_dirty": bool(dirty_paths),
        "dirty_paths": dirty_paths,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": (finished - started).total_seconds(),
        "policy_hash": file_sha256(PROJECT_ROOT / "config" / "research_settings.yaml"),
        "engine_hash": file_sha256(PROJECT_ROOT / "src" / "propstack" / "backtest" / "engine.py"),
        "contracts_hash": file_sha256(PROJECT_ROOT / "src" / "propstack" / "backtest" / "contracts.py"),
        "test_result": test_result,
        "control_evidence": list(CONTROL_EVIDENCE),
        "model_limitations": list(MODEL_LIMITATIONS),
    }

    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "engine_qualification.json"
    markdown_path = output_dir / "engine_qualification.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    print(f"{status}: {json_path.relative_to(PROJECT_ROOT)}")
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


def _markdown(report: dict) -> str:
    lines = [
        "# Engine Qualification",
        "",
        f"Software status: **{report['engine_software_status']}**",
        "",
        f"Engine contract: `{report['engine_contract_version']}`",
        f"Git commit: `{report['git_commit']}`",
        f"Dirty worktree: `{str(report['worktree_dirty']).lower()}`",
        f"Policy SHA-256: `{report['policy_hash']}`",
        "",
        "This is a software-verification result. It is not evidence that any candidate strategy is tradeable.",
        "",
        "## Control Evidence",
        "",
    ]
    for item in report["control_evidence"]:
        lines.append(f"- `{item['control']}`: {item['claim']} Evidence: `{item['evidence']}`")
    lines.extend(["", "## Model Limitations", ""])
    lines.extend(f"- {item}" for item in report["model_limitations"])
    lines.extend(["", "## Test Output", "", "```text", report["test_result"]["output"], "```", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
