from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from tempfile import NamedTemporaryFile
from typing import Any, Iterable

import numpy as np
import pandas as pd

from alphaquest.accounts.catalog import ResolvedAccountProfile
from alphaquest.accounts.models import AccountAssessmentCostsV1, AccountRuleProfileV1
from alphaquest.accounts.simulator import AccountPathEvaluation, evaluate_account_trade_path


def run_account_monte_carlo(
    trades: pd.DataFrame,
    resolved: ResolvedAccountProfile,
    *,
    costs: AccountAssessmentCostsV1 | None,
    manual_attestations: Iterable[str] = (),
    runs: int | None = None,
    seed: int = 11,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Session-block bootstrap with account state replayed independently per path."""

    profile = resolved.profile
    policy = profile.evaluation_policy
    total_runs = int(runs if runs is not None else policy.monte_carlo_runs)
    if total_runs < 1:
        raise ValueError("account Monte Carlo runs must be positive")
    input_issues = _monte_carlo_input_issues(
        trades,
        profile=profile,
        costs=costs,
        manual_attestations=manual_attestations,
    )
    if input_issues:
        return pd.DataFrame(), {
            "schema": "alphaquest.account-monte-carlo-summary/v1",
            "profile_id": profile.profile_id,
            "profile_version": profile.version,
            "profile_sha256": resolved.sha256,
            "verdict": "NEEDS MANUAL REVIEW",
            "unresolved": input_issues,
            "number_of_runs": 0,
            "seed": seed,
            "horizon_sessions": policy.monte_carlo_horizon_sessions,
            "block_sessions": policy.monte_carlo_block_sessions,
        }
    sessions = _session_frames(trades)
    if not sessions:
        return pd.DataFrame(), {
            "schema": "alphaquest.account-monte-carlo-summary/v1",
            "profile_id": profile.profile_id,
            "profile_version": profile.version,
            "profile_sha256": resolved.sha256,
            "verdict": "NEEDS MANUAL REVIEW",
            "unresolved": ["no source sessions are available"],
            "number_of_runs": 0,
        }
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    horizon = policy.monte_carlo_horizon_sessions
    block = min(policy.monte_carlo_block_sessions, len(sessions))
    for run_id in range(1, total_runs + 1):
        path = _sample_session_blocks(sessions, horizon=horizon, block=block, rng=rng)
        result = evaluate_account_trade_path(
            path,
            profile,
            costs=costs,
            manual_attestations=manual_attestations,
            evaluation_start=path["session_date"].min(),
            evaluation_end=path["session_date"].max(),
            source_evidence_session_count=len(sessions),
        ).summary
        rows.append(
            {
                "run_id": run_id,
                "verdict": result["verdict"],
                "account_closed": bool(result.get("account_closed", False)),
                "daily_loss_lock": int(result.get("daily_loss_lock_count", 0)) > 0,
                "position_rejection": int(result.get("position_rejection_count", 0)) > 0,
                "position_close_violation": int(result.get("position_close_violation_count", 0)) > 0,
                "target_reached": bool(result.get("target_reached", False)),
                "payout_count": int(result.get("payout_count", 0)),
                "gross_payouts": float(result.get("gross_payouts", 0.0)),
                "net_payout_after_costs": result.get("net_payout_after_costs"),
                "payout_to_cost_ratio": result.get("payout_to_cost_ratio"),
                "maximum_drawdown": float(result.get("maximum_drawdown", 0.0)),
                "minimum_drawdown_buffer": result.get("minimum_drawdown_buffer"),
                "sessions_to_first_payout": result.get("sessions_to_first_payout"),
                "sessions_to_target": result.get("sessions_to_target"),
            }
        )
    frame = pd.DataFrame(rows)
    summary = _monte_carlo_summary(frame, resolved, costs=costs, runs=total_runs, seed=seed)
    return frame, summary


def run_governed_account_assessment(
    trades: pd.DataFrame,
    resolved: ResolvedAccountProfile,
    output_root: str | Path,
    *,
    campaign_id: str,
    variant_id: str,
    attempt_id: str,
    config_sha256: str,
    data_sha256: str,
    strategy_implementation_sha256: str | None,
    costs: AccountAssessmentCostsV1 | None,
    source_attempt_id: str | None = None,
    manual_attestations: Iterable[str] = (),
    evaluation_start: date | str | None = None,
    evaluation_end: date | str | None = None,
    runs: int | None = None,
    seed: int = 11,
) -> dict[str, Any]:
    """Write one immutable, hash-bound destination assessment transaction."""

    attestations = sorted({str(item).strip() for item in manual_attestations if str(item).strip()})
    trade_sha256 = _frame_sha256(trades)
    identity = {
        "campaign_id": campaign_id,
        "variant_id": variant_id,
        "attempt_id": attempt_id,
        "source_attempt_id": source_attempt_id or attempt_id,
        "profile_id": resolved.profile.profile_id,
        "profile_version": resolved.profile.version,
        "profile_sha256": resolved.sha256,
        "config_sha256": config_sha256,
        "data_sha256": data_sha256,
        "strategy_implementation_sha256": strategy_implementation_sha256,
        "trade_evidence_sha256": trade_sha256,
        "costs": costs.model_dump(mode="json") if costs else None,
        "manual_attestations": attestations,
        "seed": seed,
        "runs": int(runs if runs is not None else resolved.profile.evaluation_policy.monte_carlo_runs),
    }
    assessment_id = hashlib.sha256(_canonical_json(identity)).hexdigest()[:16]
    target = (
        Path(output_root).resolve()
        / "account_evaluations"
        / _safe_segment(resolved.profile.profile_id)
        / assessment_id
    )
    if target.exists():
        raise FileExistsError(f"immutable account assessment already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{assessment_id}.", dir=target.parent))

    try:
        deterministic = evaluate_account_trade_path(
            trades,
            resolved.profile,
            costs=costs,
            manual_attestations=attestations,
            evaluation_start=evaluation_start,
            evaluation_end=evaluation_end,
        )
        mc_results, mc_summary = run_account_monte_carlo(
            trades,
            resolved,
            costs=costs,
            manual_attestations=attestations,
            runs=runs,
            seed=seed,
        )
        verdict = _combined_verdict(deterministic.summary["verdict"], mc_summary["verdict"])

        _write_json(staging / "deterministic_summary.json", deterministic.summary)
        _write_csv(staging / "violation_events.csv", deterministic.events)
        _write_csv(staging / "daily_account_path.csv", deterministic.daily)
        _write_csv(staging / "monte_carlo_results.csv", mc_results)
        _write_json(staging / "monte_carlo_summary.json", mc_summary)
        profile_snapshot = resolved.snapshot()
        _write_json(staging / "account_profile_snapshot.json", profile_snapshot)

        artifacts = {}
        for path in sorted(staging.iterdir()):
            if path.is_file():
                artifacts[path.name] = {"sha256": _file_sha256(path), "bytes": path.stat().st_size}
        manifest = {
            "schema": "alphaquest.account-assessment-manifest/v1",
            "assessment_id": assessment_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **identity,
            "verdict": verdict,
            "deterministic_verdict": deterministic.summary["verdict"],
            "monte_carlo_verdict": mc_summary["verdict"],
            "artifacts": artifacts,
        }
        _write_json(staging / "evaluation_manifest.json", manifest)
        manifest["manifest_sha256"] = _file_sha256(staging / "evaluation_manifest.json")
        os.replace(staging, target)
        manifest["assessment_path"] = str(target)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def account_suitability_row(manifest: dict[str, Any], deterministic: dict[str, Any], monte_carlo: dict[str, Any]):
    return {
        "campaign_id": manifest["campaign_id"],
        "variant_id": manifest["variant_id"],
        "attempt_id": manifest["attempt_id"],
        "source_attempt_id": manifest.get("source_attempt_id", manifest["attempt_id"]),
        "profile_id": manifest["profile_id"],
        "profile_version": manifest["profile_version"],
        "profile_sha256": manifest["profile_sha256"],
        "verdict": manifest["verdict"],
        "historical_account_closed": deterministic.get("account_closed"),
        "historical_daily_loss_locks": deterministic.get("daily_loss_lock_count"),
        "historical_position_close_violations": deterministic.get("position_close_violation_count"),
        "probability_account_closed": monte_carlo.get("probability_account_closed"),
        "probability_daily_loss_lock": monte_carlo.get("probability_daily_loss_lock"),
        "probability_position_close_violation": monte_carlo.get("probability_position_close_violation"),
        "probability_first_payout": monte_carlo.get("probability_first_payout"),
        "probability_two_payouts": monte_carlo.get("probability_two_payouts"),
        "expected_net_payout_after_costs": monte_carlo.get("expected_net_payout_after_costs"),
        "expected_payout_to_cost_ratio": monte_carlo.get("expected_payout_to_cost_ratio"),
        "expected_replacement_cost": monte_carlo.get("expected_replacement_cost"),
        "expected_net_payout_after_expected_replacement_cost": monte_carlo.get(
            "expected_net_payout_after_expected_replacement_cost"
        ),
        "p95_maximum_drawdown": monte_carlo.get("p95_maximum_drawdown"),
        "assessment_path": manifest.get("assessment_path"),
    }


def _monte_carlo_summary(
    frame: pd.DataFrame,
    resolved: ResolvedAccountProfile,
    *,
    costs: AccountAssessmentCostsV1 | None,
    runs: int,
    seed: int,
) -> dict[str, Any]:
    profile = resolved.profile
    policy = profile.evaluation_policy
    summary: dict[str, Any] = {
        "schema": "alphaquest.account-monte-carlo-summary/v1",
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "profile_sha256": resolved.sha256,
        "number_of_runs": runs,
        "seed": seed,
        "horizon_sessions": policy.monte_carlo_horizon_sessions,
        "block_sessions": policy.monte_carlo_block_sessions,
        "probability_account_closed": float(frame["account_closed"].mean()),
        "probability_daily_loss_lock": float(frame["daily_loss_lock"].mean()),
        "probability_position_rejection": float(frame["position_rejection"].mean()),
        "probability_position_close_violation": float(frame["position_close_violation"].mean()),
        "probability_manual_review": float((frame["verdict"] == "NEEDS MANUAL REVIEW").mean()),
        "probability_target_reached": float(frame["target_reached"].mean()),
        "probability_first_payout": float((frame["payout_count"] >= 1).mean()),
        "probability_two_payouts": float((frame["payout_count"] >= 2).mean()),
        "expected_gross_payouts": float(frame["gross_payouts"].mean()),
        "p95_maximum_drawdown": float(frame["maximum_drawdown"].quantile(0.95)),
        "median_minimum_drawdown_buffer": _finite_median(frame["minimum_drawdown_buffer"]),
        "median_sessions_to_first_payout": _finite_median(frame["sessions_to_first_payout"]),
        "median_sessions_to_target": _finite_median(frame["sessions_to_target"]),
        "costs_included": costs is not None,
        "criteria": [],
        "unresolved": [],
    }
    if runs < policy.monte_carlo_runs:
        summary["unresolved"].append(
            f"only {runs} Monte Carlo paths were run; the governed profile requires {policy.monte_carlo_runs}"
        )
    if costs is not None:
        summary["expected_net_payout_after_costs"] = float(
            pd.to_numeric(frame["net_payout_after_costs"], errors="coerce").mean()
        )
        summary["expected_payout_to_cost_ratio"] = (
            float(frame["gross_payouts"].mean()) / costs.total if costs.total > 0 else None
        )
        expected_replacement_cost = (
            summary["probability_account_closed"] * costs.total
            if costs.include_as_replacement_cost
            else 0.0
        )
        summary["expected_replacement_cost"] = float(expected_replacement_cost)
        summary["expected_net_payout_after_expected_replacement_cost"] = float(
            frame["gross_payouts"].mean() - expected_replacement_cost
        )
    else:
        summary["expected_net_payout_after_costs"] = None
        summary["expected_payout_to_cost_ratio"] = None
        summary["expected_replacement_cost"] = None
        summary["expected_net_payout_after_expected_replacement_cost"] = None
    if profile.identity.account_kind == "prop_challenge":
        pass_probability = summary["probability_target_reached"]
        summary["expected_evaluation_purchases_per_pass"] = (
            1.0 / pass_probability if pass_probability > 0 else None
        )
        summary["expected_failed_evaluations_before_pass"] = (
            (1.0 - pass_probability) / pass_probability if pass_probability > 0 else None
        )
        summary["expected_evaluation_fees_per_pass"] = (
            costs.evaluation_purchase_price / pass_probability
            if costs is not None and pass_probability > 0
            else None
        )
    if summary["probability_manual_review"] > 0:
        summary["unresolved"].append("one or more Monte Carlo paths had incomplete account evidence")

    criteria = [
        _criterion(
            "probability_account_closed",
            summary["probability_account_closed"],
            "max",
            policy.maximum_account_closure_probability,
        ),
        _criterion(
            "probability_daily_loss_lock",
            summary["probability_daily_loss_lock"],
            "max",
            policy.maximum_daily_loss_lock_probability,
        ),
    ]
    if profile.identity.account_kind == "prop_challenge":
        criteria.append(
            _criterion(
                "probability_target_reached",
                summary["probability_target_reached"],
                "min",
                1.0 - policy.maximum_account_closure_probability,
            )
        )
    if policy.minimum_first_payout_probability is not None:
        criteria.append(
            _criterion(
                "probability_first_payout",
                summary["probability_first_payout"],
                "min",
                policy.minimum_first_payout_probability,
            )
        )
    if policy.minimum_two_payout_probability is not None:
        criteria.append(
            _criterion(
                "probability_two_payouts",
                summary["probability_two_payouts"],
                "min",
                policy.minimum_two_payout_probability,
            )
        )
    if policy.maximum_p95_drawdown is not None:
        criteria.append(
            _criterion(
                "p95_maximum_drawdown",
                summary["p95_maximum_drawdown"],
                "max",
                policy.maximum_p95_drawdown,
            )
        )
    if policy.minimum_expected_net_payout_after_costs is not None:
        if costs is None:
            summary["unresolved"].append("expected payout after costs requires timestamped checkout costs")
        else:
            criteria.append(
                _criterion(
                    "expected_net_payout_after_costs",
                    summary["expected_net_payout_after_costs"],
                    "exclusive_min",
                    policy.minimum_expected_net_payout_after_costs,
                )
            )
    if policy.minimum_expected_payout_to_cost_ratio is not None:
        if costs is None or costs.total <= 0:
            summary["unresolved"].append("payout-to-cost ratio requires positive timestamped checkout costs")
        else:
            criteria.append(
                _criterion(
                    "expected_payout_to_cost_ratio",
                    summary["expected_payout_to_cost_ratio"],
                    "min",
                    policy.minimum_expected_payout_to_cost_ratio,
                )
            )
    summary["criteria"] = criteria
    summary["verdict"] = (
        "NEEDS MANUAL REVIEW"
        if summary["unresolved"]
        else "PASS"
        if all(item["passed"] for item in criteria)
        else "FAIL"
    )
    return summary


def _session_frames(trades: pd.DataFrame) -> list[pd.DataFrame]:
    if "session_date" not in trades.columns:
        return []
    dates = pd.to_datetime(trades["session_date"], errors="coerce")
    if dates.isna().any():
        return []
    frame = trades.copy()
    frame["session_date"] = dates.dt.date
    if "intraday_min_equity" in frame.columns:
        if "intratrade_min_pnl" not in frame.columns and "account_equity_before_entry" in frame.columns:
            frame["intratrade_min_pnl"] = pd.to_numeric(
                frame["intraday_min_equity"], errors="coerce"
            ) - pd.to_numeric(frame["account_equity_before_entry"], errors="coerce")
        # Absolute equity belongs to the historical path and must never be
        # carried into a resampled path with a different starting balance.
        frame = frame.drop(columns=["intraday_min_equity"])
    return [group.copy() for _, group in frame.groupby("session_date", sort=True)]


def _monte_carlo_input_issues(
    trades: pd.DataFrame,
    *,
    profile: AccountRuleProfileV1,
    costs: AccountAssessmentCostsV1 | None,
    manual_attestations: Iterable[str],
) -> list[str]:
    issues: list[str] = []
    if "session_date" not in trades.columns:
        return ["trade log is missing session_date"]
    dates = pd.to_datetime(trades["session_date"], errors="coerce")
    if dates.isna().any():
        return ["trade log contains invalid session_date values"]
    source_sessions = int(dates.dt.date.nunique())
    minimum_sessions = profile.evaluation_policy.minimum_horizon_sessions
    if source_sessions < minimum_sessions:
        issues.append(
            f"only {source_sessions} source sessions are available; {minimum_sessions} are required before account Monte Carlo"
        )
    relative_columns = [name for name in ("intratrade_min_pnl", "mae_currency") if name in trades.columns]
    point_columns = {"max_adverse_excursion", "point_value", "contracts"}
    absolute_columns = {"intraday_min_equity", "account_equity_before_entry"}
    missing_excursion_rows = 0
    for _, row in trades.iterrows():
        relative = any(pd.notna(row.get(name)) for name in relative_columns)
        point = point_columns.issubset(trades.columns) and all(pd.notna(row.get(name)) for name in point_columns)
        absolute = absolute_columns.issubset(trades.columns) and all(
            pd.notna(row.get(name)) for name in absolute_columns
        )
        if not (relative or point or absolute):
            missing_excursion_rows += 1
    if missing_excursion_rows:
        issues.append(
            "account Monte Carlo requires a path-relative adverse excursion for every trade; "
            f"{missing_excursion_rows} rows cannot be resampled"
        )
    if not profile.rules.overnight_positions_allowed and not (
        "exit_timestamp" in trades.columns or "forced_flatten_compliant" in trades.columns
    ):
        issues.append("account Monte Carlo requires exit_timestamp or forced_flatten_compliant")
    cost_required = (
        profile.rules.acquisition.evaluation_price_mode == "assessment_input_required"
        or profile.rules.acquisition.activation_fee_mode == "assessment_input_required"
    )
    if cost_required and costs is None:
        issues.append("timestamped checkout evaluation and activation costs are required")
    provided = {str(item).strip() for item in manual_attestations if str(item).strip()}
    missing_attestations = sorted(set(profile.rules.manual_attestations_required) - provided)
    if missing_attestations:
        issues.append("missing manual attestations: " + ", ".join(missing_attestations))
    return issues


def _sample_session_blocks(sessions, *, horizon: int, block: int, rng) -> pd.DataFrame:
    selected = []
    while len(selected) < horizon:
        start = int(rng.integers(0, max(1, len(sessions) - block + 1)))
        selected.extend(sessions[start : start + block])
    selected = selected[:horizon]
    dates = _weekday_dates(date(2020, 1, 2), horizon)
    rows = []
    for target_date, source in zip(dates, selected):
        copy = source.copy()
        copy["source_session_date"] = copy["session_date"].astype(str)
        copy["session_date"] = target_date
        rows.append(copy)
    return pd.concat(rows, ignore_index=True)


def _weekday_dates(start: date, count: int) -> list[date]:
    dates = []
    current = start
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def _criterion(metric: str, actual: float, operator: str, threshold: float) -> dict[str, Any]:
    passed = actual <= threshold if operator == "max" else actual > threshold if operator == "exclusive_min" else actual >= threshold
    return {
        "metric": metric,
        "actual": float(actual),
        "operator": operator,
        "threshold": float(threshold),
        "passed": bool(passed),
    }


def _combined_verdict(deterministic: str, stochastic: str) -> str:
    if "NEEDS MANUAL REVIEW" in {deterministic, stochastic}:
        return "NEEDS MANUAL REVIEW"
    if "FAIL" in {deterministic, stochastic}:
        return "FAIL"
    return "PASS"


def _finite_median(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.median()) if len(values) else None


def _frame_sha256(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    normalized = normalized.reindex(sorted(normalized.columns), axis=1)
    data = normalized.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _safe_segment(value: str) -> str:
    return value.replace("/", "__").replace("@", "_")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    _atomic_write(path, frame.to_csv(index=False, lineterminator="\n"))


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


__all__ = [
    "account_suitability_row",
    "run_account_monte_carlo",
    "run_governed_account_assessment",
]
