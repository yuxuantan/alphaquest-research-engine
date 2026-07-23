"""Compare fixed-default Yush outputs on Databento and Sierra event sources."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.data.databento_session_stream import iter_databento_trade_sessions
from alphaquest.data.sierra_session_stream import iter_sierra_trade_sessions
from alphaquest.strategy_modules.event import build_event_strategy
from alphaquest.strategy_certification import get_strategy_certification
from alphaquest.utils.hashing import file_sha256


CANDIDATE = Path("data/reports/data_quality/ES/yush_sierra_event_dataset_candidate_v5")
DEFAULT_CONFIG = Path(
    "research/campaigns/active/yush_orderflow_range/follow_up_attempts/"
    "pre_pnl_parameter_declaration_20260722t073725_983024c1/v01/config.yaml"
)
DEFAULT_OUTPUT = Path(
    "data/reports/data_quality/ES/"
    "yush_sierra_fixed_default_concordance_v4_stratified_v4_20250715_20260529"
)
RAW_DIR = Path("data/raw/ES/sierra-es-trades")
ROLL_CALENDAR = Path("data/reference/ES/roll_calendars/motivewave_rithmic_roll_calendar.csv")
DATABENTO_ARCHIVE = Path("data/raw/ES/GLBX-20260713-S6XF67C8UA.zip")
FULL_SESSION_AUDIT = Path(
    "data/reports/data_quality/ES/"
    "databento_sierra_full_session_orderflow_20250714_20260610/summary.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--stratified-session-count",
        type=int,
        default=20,
        help=(
            "Deterministic, evenly spaced output-concordance sessions. The exhaustive "
            "event-stream audit remains the proof for every eligible overlap session."
        ),
    )
    parser.add_argument(
        "--required-session-date",
        action="append",
        default=[],
        help="Always include this known risk or trade-producing session (repeatable).",
    )
    parser.add_argument("--minimum-concordant-trades", type=int, default=5)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume only from a hash- and session-bound Databento checkpoint.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.project_root.resolve()
    output = _resolve(root, args.output_dir)
    if output.exists() and any(output.iterdir()) and not args.resume:
        raise FileExistsError(f"concordance output already exists and will not be overwritten: {output}")
    if args.resume and (output / "concordance_report.json").exists():
        raise FileExistsError(f"concordance report is already complete and immutable: {output}")
    output.mkdir(parents=True, exist_ok=True)
    config_path = _resolve(root, args.config)
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    certification = get_strategy_certification("yush_orderflow_range", root, require_current=True)
    cfg["strategy_certification"] = {
        "strategy_id": certification.strategy_id,
        "implementation_version": certification.implementation_version,
        "implementation_sha256": certification.implementation_sha256,
        "manifest_sha256": certification.manifest_sha256,
    }
    capability_path = root / CANDIDATE / "event_capabilities.csv"
    levels_path = root / CANDIDATE / "session_levels.parquet"
    raw_manifest_path = root / CANDIDATE / "raw_manifest.json"
    capability = pd.read_csv(capability_path, dtype={"session_date": "string"})
    compared = capability[capability["reference_tier"].eq("databento_compared")].copy()
    eligible = compared[compared["full_strategy_events_extrapolated"].map(_as_bool)].copy()
    first_databento_session = str(compared["session_date"].min())
    warmup_excluded = eligible["session_date"].eq(first_databento_session)
    eligible = eligible.loc[~warmup_excluded].copy()
    eligible_session_dates = sorted(set(eligible["session_date"].astype(str)))
    if not eligible_session_dates:
        raise ValueError("candidate capability contains no Databento-compared eligible sessions")
    session_dates = _selected_session_dates(
        eligible_session_dates,
        count=args.stratified_session_count,
        required=args.required_session_date,
    )
    start, end = min(session_dates), max(session_dates)

    config_sha256 = file_sha256(config_path)
    capability_sha256 = file_sha256(capability_path)
    databento_levels: list[dict] = []
    sierra_levels: list[dict] = []
    sierra_config = {
        "source": "sierra_scid_records",
        "raw_dir": str((root / RAW_DIR).resolve()),
        "raw_manifest": str(raw_manifest_path),
        "session_levels": str(levels_path),
        "quality_manifest": str(capability_path),
        "required_capability": "full_strategy_events_extrapolated",
        "ineligible_session_policy": "blackout",
        "roll_calendar": str(root / ROLL_CALENDAR),
        "root_symbol": "ES",
        "rth_start": "09:30:00",
        "rth_end": "11:00:00",
        "verified_window_start": "09:30:00",
        "verified_window_end": "11:00:00",
    }
    sc_sessions = _record_levels(
        (
            session
            for session in iter_sierra_trade_sessions(
                sierra_config, start_date=start, end_date=end
            )
            if str(session.session_date) in session_dates
        ),
        sierra_levels,
    )

    if args.resume:
        db_trades, db_audits, databento_levels = _load_databento_checkpoint(
            output,
            config_sha256=config_sha256,
            capability_sha256=capability_sha256,
            session_dates=session_dates,
        )
    else:
        db_sessions = _record_levels(
            (
                session
                for session in iter_databento_trade_sessions(
                    root / DATABENTO_ARCHIVE,
                    root / ROLL_CALENDAR,
                    start_date=start,
                    end_date=end,
                    root_symbol="ES",
                    reset_previous_levels_on_roll=True,
                    overnight_start="16:00:00",
                )
                if str(session.session_date) in session_dates
            ),
            databento_levels,
        )
        db_result = BacktestEngine(cfg, show_progress=True).run_event_replay(
            db_sessions, build_event_strategy(cfg)
        )
        db_trades = db_result["trades"].copy()
        db_audits = db_result["session_audits"].copy()
        _write_databento_checkpoint(
            output,
            config_sha256=config_sha256,
            capability_sha256=capability_sha256,
            session_dates=session_dates,
            trades=db_trades,
            session_audits=db_audits,
            levels=databento_levels,
        )
    sc_result = BacktestEngine(cfg, show_progress=True).run_event_replay(
        sc_sessions, build_event_strategy(cfg)
    )
    sc_trades = sc_result["trades"].copy()
    sc_audits = sc_result["session_audits"].copy()

    level_comparison = _compare_levels(databento_levels, sierra_levels)
    trade_comparison = _compare_trades(db_trades, sc_trades)
    audit_comparison = _compare_session_audits(db_audits, sc_audits)
    level_comparison.to_csv(output / "level_comparison.csv", index=False)
    trade_comparison.to_csv(output / "trade_comparison.csv", index=False)
    audit_comparison.to_csv(output / "session_audit_comparison.csv", index=False)
    db_trades.to_parquet(output / "databento_trades.parquet", index=False)
    sc_trades.to_parquet(output / "sierra_trades.parquet", index=False)

    level_pass = bool(len(level_comparison) == len(session_dates) and level_comparison["exact"].all())
    trade_pass = bool(trade_comparison.empty or trade_comparison["exact"].all())
    audit_pass = bool(
        len(audit_comparison) == len(session_dates)
        and audit_comparison["decision_path_exact"].all()
    )
    all_diagnostics_exact = bool(
        len(audit_comparison) == len(session_dates) and audit_comparison["exact"].all()
    )
    trade_coverage_pass = bool(
        len(db_trades) >= args.minimum_concordant_trades
        and len(sc_trades) >= args.minimum_concordant_trades
    )
    verdict = (
        "PASS"
        if level_pass and trade_pass and audit_pass and trade_coverage_pass
        else "NEEDS MANUAL REVIEW"
    )
    report = {
        "schema": "alphaquest.strategy-source-concordance/v1",
        "verdict": verdict,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "strategy_id": "yush_orderflow_range",
        "strategy_certification": {
            "implementation_version": certification.implementation_version,
            "implementation_sha256": certification.implementation_sha256,
            "manifest_sha256": certification.manifest_sha256,
        },
        "parameter_mode": "declared_defaults",
        "config": str(config_path.relative_to(root)),
        "config_sha256": config_sha256,
        "scope": {
            "start_date": start,
            "end_date": end,
            "databento_compared_sessions": int(len(compared)),
            "eligible_exact_event_sessions": int(len(eligible_session_dates)),
            "output_concordance_sessions": int(len(session_dates)),
            "output_concordance_session_dates": sorted(session_dates),
            "selection": "evenly_spaced_stratified_plus_predeclared_required_dates",
            "minimum_concordant_trades": int(args.minimum_concordant_trades),
            "blackout_sessions": int(len(compared) - len(eligible_session_dates)),
            "reference_warmup_excluded_sessions": int(warmup_excluded.sum()),
        },
        "checks": {
            "sampled_completed_bar_market_levels_exact": level_pass,
            "sampled_fixed_default_trade_semantics_exact": trade_pass,
            "sampled_fixed_default_decision_path_exact": audit_pass,
            "sampled_all_internal_diagnostic_counters_exact": all_diagnostics_exact,
            "minimum_trade_coverage_met": trade_coverage_pass,
            "all_eligible_overlap_event_inputs_prequalified": bool(
                len(eligible_session_dates) > 0
            ),
        },
        "outcome": {
            "databento_trades": int(len(db_trades)),
            "sierra_trades": int(len(sc_trades)),
            "level_mismatches": int((~level_comparison["exact"]).sum()) if len(level_comparison) else 0,
            "trade_mismatches": int((~trade_comparison["exact"]).sum()) if len(trade_comparison) else 0,
            "session_audit_mismatches": int((~audit_comparison["exact"]).sum()) if len(audit_comparison) else 0,
            "decision_path_mismatches": (
                int((~audit_comparison["decision_path_exact"]).sum())
                if len(audit_comparison)
                else 0
            ),
        },
        "source_hashes": {
            str(DATABENTO_ARCHIVE): file_sha256(root / DATABENTO_ARCHIVE),
            str(ROLL_CALENDAR): file_sha256(root / ROLL_CALENDAR),
            str(CANDIDATE / "event_capabilities.csv"): file_sha256(capability_path),
            str(CANDIDATE / "session_levels.parquet"): file_sha256(levels_path),
            str(CANDIDATE / "raw_manifest.json"): file_sha256(raw_manifest_path),
            str(FULL_SESSION_AUDIT): (
                file_sha256(root / FULL_SESSION_AUDIT)
                if (root / FULL_SESSION_AUDIT).is_file()
                else None
            ),
        },
        "policy": {
            "outside_entry_window": "compare only PDH/PDL/PDC and ONH/ONL completed-bar levels",
            "entry_window": "use dates with exact reconstructed event equivalence from 09:30-11:00 ET",
            "output_concordance": (
                "replay a deterministic stratified sample including predeclared trade-producing "
                "dates; require exact levels, decisions, orders, risk gates, and trades; retain "
                "sub-millisecond drift in pre-order exploratory counters as non-passing diagnostics"
            ),
            "known_non_equivalent_dates": "blackout",
            "first_overlap_session": (
                "excluded from strategy-output concordance because the Databento archive "
                "does not include its previous RTH session"
            ),
            "older_history": "permit only intrinsic Sierra structure-pass sessions as an explicit extrapolation",
        },
        "blackout_sessions": int(len(compared) - len(eligible_session_dates)),
    }
    report_path = output / "concordance_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


def _record_levels(sessions: Iterable, rows: list[dict]):
    for session in sessions:
        prior = session.previous_rth
        rows.append(
            {
                "session_date": str(session.session_date),
                "contract_symbol": _canonical_contract(str(session.contract_symbol)),
                "previous_rth_session_date": None if prior is None else str(prior.session_date),
                "previous_rth_contract_symbol": (
                    None
                    if prior is None
                    else _canonical_contract(str(prior.contract_symbol))
                ),
                "previous_rth_high": None if prior is None else float(prior.high),
                "previous_rth_low": None if prior is None else float(prior.low),
                "previous_rth_close": None if prior is None else float(prior.close),
                "overnight_high": session.overnight_high,
                "overnight_low": session.overnight_low,
            }
        )
        yield session


def _selected_session_dates(
    eligible: list[str],
    *,
    count: int,
    required: list[str],
) -> set[str]:
    if count < 1:
        raise ValueError("--stratified-session-count must be positive")
    if not eligible:
        return set()
    eligible_set = set(eligible)
    unknown = sorted(set(required) - eligible_set)
    if unknown:
        raise ValueError(f"required concordance sessions are not eligible: {unknown}")
    sample_size = min(count, len(eligible))
    indexes = np.linspace(0, len(eligible) - 1, num=sample_size, dtype=int)
    return {eligible[int(index)] for index in indexes} | set(required)


def _write_databento_checkpoint(
    output: Path,
    *,
    config_sha256: str,
    capability_sha256: str,
    session_dates: set[str],
    trades: pd.DataFrame,
    session_audits: pd.DataFrame,
    levels: list[dict],
) -> None:
    trades.to_parquet(output / "databento_trades.checkpoint.parquet", index=False)
    session_audits.to_parquet(
        output / "databento_session_audits.checkpoint.parquet", index=False
    )
    pd.DataFrame(levels).to_csv(output / "databento_levels.checkpoint.csv", index=False)
    (output / "databento_checkpoint.json").write_text(
        json.dumps(
            {
                "schema": "alphaquest.strategy-source-concordance-checkpoint/v1",
                "status": "DATABENTO_REPLAY_COMPLETE",
                "config_sha256": config_sha256,
                "capability_sha256": capability_sha256,
                "session_dates": sorted(session_dates),
                "trades": len(trades),
                "session_audits": len(session_audits),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _load_databento_checkpoint(
    output: Path,
    *,
    config_sha256: str,
    capability_sha256: str,
    session_dates: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    manifest_path = output / "databento_checkpoint.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"--resume requires Databento checkpoint: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        "schema": "alphaquest.strategy-source-concordance-checkpoint/v1",
        "status": "DATABENTO_REPLAY_COMPLETE",
        "config_sha256": config_sha256,
        "capability_sha256": capability_sha256,
        "session_dates": sorted(session_dates),
    }
    mismatched = [
        key for key, value in expected.items() if manifest.get(key) != value
    ]
    if mismatched:
        raise ValueError(
            f"Databento checkpoint does not match current concordance inputs: {mismatched}"
        )
    trades = pd.read_parquet(output / "databento_trades.checkpoint.parquet")
    session_audits = pd.read_parquet(
        output / "databento_session_audits.checkpoint.parquet"
    )
    levels = pd.read_csv(
        output / "databento_levels.checkpoint.csv",
        dtype={
            "session_date": "string",
            "previous_rth_session_date": "string",
            "contract_symbol": "string",
            "previous_rth_contract_symbol": "string",
        },
    ).to_dict(orient="records")
    if len(trades) != int(manifest.get("trades", -1)):
        raise ValueError("Databento trade checkpoint row count is stale or corrupted")
    if len(session_audits) != int(manifest.get("session_audits", -1)):
        raise ValueError("Databento session-audit checkpoint row count is stale or corrupted")
    if {str(row["session_date"]) for row in levels} != session_dates:
        raise ValueError("Databento level checkpoint session coverage is stale or corrupted")
    return trades, session_audits, levels


def _compare_levels(left: list[dict], right: list[dict]) -> pd.DataFrame:
    keys = ["session_date", "contract_symbol"]
    merged = pd.DataFrame(left).merge(
        pd.DataFrame(right),
        on=keys,
        how="outer",
        suffixes=("_databento", "_sierra"),
        indicator=True,
    )
    fields = [
        "previous_rth_session_date",
        "previous_rth_contract_symbol",
        "previous_rth_high",
        "previous_rth_low",
        "previous_rth_close",
        "overnight_high",
        "overnight_low",
    ]
    exact = merged["_merge"].eq("both")
    for field in fields:
        left_value = merged[f"{field}_databento"]
        right_value = merged[f"{field}_sierra"]
        if field.endswith(("high", "low", "close")):
            match = np.isclose(
                pd.to_numeric(left_value, errors="coerce"),
                pd.to_numeric(right_value, errors="coerce"),
                rtol=0,
                atol=1e-9,
                equal_nan=True,
            )
        else:
            match = left_value.fillna("<NONE>").astype(str).eq(
                right_value.fillna("<NONE>").astype(str)
            )
        merged[f"{field}_exact"] = match
        exact &= match
    merged["exact"] = exact
    return merged


def _compare_trades(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    left = _trade_keys(left, "databento")
    right = _trade_keys(right, "sierra")
    keys = ["session_date", "session_trade_number"]
    merged = left.merge(right, on=keys, how="outer", suffixes=("_databento", "_sierra"), indicator=True)
    if merged.empty:
        return pd.DataFrame(columns=[*keys, "exact"])
    semantic = [
        "direction",
        "entry_trigger_price",
        "entry_price",
        "exit_price",
        "initial_stop_price",
        "stop_price",
        "target_price",
        "exit_reason",
        "risk_points",
        "net_pnl",
        "aoi_side",
        "aoi_box_low",
        "aoi_box_high",
        "aoi_categories",
        "aoi_confluences",
        "trigger_kind",
        "trigger_value",
        "entry_profile_poc",
        "entry_profile_vah",
        "entry_profile_val",
        "midpoint_activated",
        "aoi_exact_fingerprint",
    ]
    exact = merged["_merge"].eq("both")
    for field in semantic:
        lcol, rcol = f"{field}_databento", f"{field}_sierra"
        if lcol not in merged or rcol not in merged:
            exact &= False
            continue
        if pd.api.types.is_numeric_dtype(merged[lcol]) or pd.api.types.is_numeric_dtype(merged[rcol]):
            match = np.isclose(
                pd.to_numeric(merged[lcol], errors="coerce"),
                pd.to_numeric(merged[rcol], errors="coerce"),
                rtol=0,
                atol=1e-9,
                equal_nan=True,
            )
        else:
            match = merged[lcol].fillna("<NONE>").astype(str).eq(
                merged[rcol].fillna("<NONE>").astype(str)
            )
        merged[f"{field}_exact"] = match
        exact &= match
    merged["exact"] = exact
    return merged


def _trade_keys(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    out = frame.copy()
    if out.empty:
        return pd.DataFrame(columns=["session_date", "session_trade_number"])
    out["session_date"] = out["session_date"].astype(str)
    out["session_trade_number"] = out.groupby("session_date").cumcount() + 1
    out["source"] = source
    return out


def _compare_session_audits(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    left = left.copy()
    right = right.copy()
    left["contract_symbol"] = left["contract_symbol"].astype(str).map(
        _canonical_contract
    )
    right["contract_symbol"] = right["contract_symbol"].astype(str).map(
        _canonical_contract
    )
    keys = ["session_date", "contract_symbol"]
    left = left.copy()
    right = right.copy()
    left["session_date"] = left["session_date"].astype(str)
    right["session_date"] = right["session_date"].astype(str)
    merged = left.merge(right, on=keys, how="outer", suffixes=("_databento", "_sierra"), indicator=True)
    fields = [
        column
        for column in left.columns
        if column not in {*keys, "input_was_canonically_sorted", "canonical_event_order"}
        and column in right.columns
    ]
    exploratory_counters = {
        "taps",
        "delta_bubbles",
        "wrong_approach_rejections",
    }
    exact = merged["_merge"].eq("both")
    decision_path_exact = merged["_merge"].eq("both")
    for field in fields:
        lcol, rcol = f"{field}_databento", f"{field}_sierra"
        match = merged[lcol].fillna("<NONE>").astype(str).eq(
            merged[rcol].fillna("<NONE>").astype(str)
        )
        merged[f"{field}_exact"] = match
        exact &= match
        if field not in exploratory_counters:
            decision_path_exact &= match
    merged["exact"] = exact
    merged["decision_path_exact"] = decision_path_exact
    return merged


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _canonical_contract(value: str) -> str:
    value = str(value).strip().upper()
    digits = "".join(character for character in value if character.isdigit())
    prefix = value[: len(value) - len(digits)]
    if len(digits) == 2:
        digits = digits[-1]
    if len(digits) != 1:
        raise ValueError(f"unexpected ES contract symbol: {value!r}")
    return f"{prefix}{digits}"


def _resolve(root: Path, value: Path) -> Path:
    return value if value.is_absolute() else root / value


if __name__ == "__main__":
    main()
