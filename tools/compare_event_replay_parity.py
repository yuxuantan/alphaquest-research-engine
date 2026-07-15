from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


FRAME_ARTIFACTS = ("core/trade_log.csv", "core/session_audits.csv")
METRIC_FIELDS = (
    "total_trades",
    "net_profit",
    "profit_factor",
    "expectancy_per_trade",
    "expectancy_r",
    "max_drawdown",
    "max_drawdown_pct",
    "win_rate",
    "trades_per_year",
    "max_consecutive_losses",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare a migrated event-replay run against its frozen reference artifacts."
    )
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = compare_runs(args.baseline, args.candidate)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")
    if report["status"] != "PASS":
        raise SystemExit(1)


def compare_runs(baseline: Path, candidate: Path) -> dict:
    artifact_reports = {}
    passed = True
    for relative in FRAME_ARTIFACTS:
        baseline_path = baseline / relative
        candidate_path = candidate / relative
        comparison = _compare_frame(baseline_path, candidate_path)
        artifact_reports[relative] = comparison
        passed = passed and comparison["passed"]

    metrics = _compare_metrics(
        baseline / "core" / "metrics.json",
        candidate / "core" / "metrics.json",
    )
    passed = passed and metrics["passed"]
    return {
        "status": "PASS" if passed else "FAIL",
        "comparison_contract": "baseline_columns_and_headline_metrics_v1",
        "baseline": str(baseline),
        "candidate": str(candidate),
        "artifacts": artifact_reports,
        "metrics": metrics,
    }


def _compare_frame(baseline_path: Path, candidate_path: Path) -> dict:
    if not baseline_path.is_file() or not candidate_path.is_file():
        return {
            "passed": False,
            "error": "missing artifact",
            "baseline_exists": baseline_path.is_file(),
            "candidate_exists": candidate_path.is_file(),
        }
    baseline = pd.read_csv(baseline_path)
    candidate = pd.read_csv(candidate_path)
    missing_columns = [column for column in baseline.columns if column not in candidate.columns]
    row_count_match = len(baseline) == len(candidate)
    mismatches = {}
    if row_count_match:
        for column in baseline.columns:
            if column in missing_columns:
                continue
            mismatch = _column_mismatch(baseline[column], candidate[column], column)
            if mismatch is not None:
                mismatches[column] = mismatch
    passed = row_count_match and not missing_columns and not mismatches
    baseline_hash = _contract_hash(baseline, list(baseline.columns))
    candidate_hash = (
        _contract_hash(candidate, list(baseline.columns)) if not missing_columns else None
    )
    return {
        "passed": passed,
        "baseline_rows": int(len(baseline)),
        "candidate_rows": int(len(candidate)),
        "baseline_columns": int(len(baseline.columns)),
        "candidate_columns": int(len(candidate.columns)),
        "missing_baseline_columns": missing_columns,
        "column_mismatches": mismatches,
        "baseline_contract_sha256": baseline_hash,
        "candidate_contract_sha256": candidate_hash,
    }


def _column_mismatch(baseline: pd.Series, candidate: pd.Series, column: str) -> dict | None:
    if _is_timestamp_column(column):
        left = pd.to_datetime(baseline, utc=True, format="mixed", errors="coerce")
        right = pd.to_datetime(candidate, utc=True, format="mixed", errors="coerce")
        equal = (left == right) | (left.isna() & right.isna())
    elif pd.api.types.is_numeric_dtype(baseline) and not pd.api.types.is_bool_dtype(baseline):
        left = pd.to_numeric(baseline, errors="coerce").to_numpy(dtype=float)
        right = pd.to_numeric(candidate, errors="coerce").to_numpy(dtype=float)
        equal = pd.Series(np.isclose(left, right, rtol=0.0, atol=1e-10, equal_nan=True))
    else:
        left = baseline.astype("string").fillna("<NULL>")
        right = candidate.astype("string").fillna("<NULL>")
        equal = left == right
    if bool(equal.all()):
        return None
    indexes = np.flatnonzero(~np.asarray(equal, dtype=bool))
    examples = [
        {
            "row": int(index),
            "baseline": _display_value(baseline.iloc[index]),
            "candidate": _display_value(candidate.iloc[index]),
        }
        for index in indexes[:5]
    ]
    return {"count": int(len(indexes)), "examples": examples}


def _compare_metrics(baseline_path: Path, candidate_path: Path) -> dict:
    baseline = json.loads(baseline_path.read_text())
    candidate = json.loads(candidate_path.read_text())
    mismatches = {}
    for field in METRIC_FIELDS:
        left = baseline.get(field)
        right = candidate.get(field)
        if not _metric_equal(left, right):
            mismatches[field] = {"baseline": left, "candidate": right}
    return {"passed": not mismatches, "fields": list(METRIC_FIELDS), "mismatches": mismatches}


def _metric_equal(left, right) -> bool:
    if left is None or right is None:
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-10)
    return left == right


def _contract_hash(frame: pd.DataFrame, columns: list[str]) -> str:
    digest = hashlib.sha256()
    for column in columns:
        digest.update(column.encode())
        digest.update(b"\0")
        series = frame[column]
        if _is_timestamp_column(column):
            values = pd.to_datetime(series, utc=True, format="mixed", errors="coerce")
            normalized = ["<NULL>" if pd.isna(value) else str(int(value.value)) for value in values]
        elif pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            normalized = ["<NULL>" if pd.isna(value) else format(float(value), ".15g") for value in series]
        else:
            normalized = series.astype("string").fillna("<NULL>").tolist()
        for value in normalized:
            digest.update(str(value).encode())
            digest.update(b"\n")
    return digest.hexdigest()


def _is_timestamp_column(column: str) -> bool:
    return "timestamp" in column or column.endswith("_at")


def _display_value(value):
    return None if pd.isna(value) else value.item() if isinstance(value, np.generic) else value


if __name__ == "__main__":
    main()
