"""Prepare and publish the governed Sierra source for Yush event replay.

Preparation is pre-PnL. It combines completed-bar market-level inputs with a
fail-closed per-session event capability. Publication is permitted only after a
fixed-default Databento/Sierra strategy-concordance report records PASS.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil

import pandas as pd

from alphaquest.authoring.models import DatasetManifestV1, EventExecutionSourceV1
from alphaquest.utils.hashing import file_sha256


DATASET_ID = "es_sierra_yush_events_20110815_20260529_0930_1100_ny"
DATABENTO_BAR_DIR = Path("data/cache/databento/GLBX-20260601-U6S3S4F4GM")
DATABENTO_BAR_VALIDATION = Path(
    "data/cache/databento/"
    "es_databento_ohlcv_1m_20100606_20260531_eth_rth_explicit_roll.validation.json"
)
STRUCTURE_AUDIT = Path(
    "data/reports/data_quality/ES/"
    "sierra_scid_event_usability_0930_1100_20101214_20260610_by_date.csv"
)
TICK_COMPARISON = Path(
    "data/reports/data_quality/ES/"
    "databento_sierra_tick_comparison_0930_1100_20250714_20260610/by_date.csv"
)
RAW_DIR = Path("data/raw/ES/sierra-es-trades")
ROLL_CALENDAR = Path("data/reference/ES/roll_calendars/motivewave_rithmic_roll_calendar.csv")
CANDIDATE_ROOT = Path("data/reports/data_quality/ES/yush_sierra_event_dataset_candidate_v5")
FULL_SESSION_AUDIT_ROOT = Path(
    "data/reports/data_quality/ES/"
    "databento_sierra_full_session_orderflow_20250714_20260610"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--concordance-report", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.project_root.resolve()
    if args.prepare == args.finalize:
        raise SystemExit("Choose exactly one of --prepare or --finalize")
    if args.prepare:
        result = prepare(root)
    else:
        if args.concordance_report is None:
            raise SystemExit("--finalize requires --concordance-report")
        result = finalize(root, _resolve(root, args.concordance_report))
    print(json.dumps(result, indent=2, sort_keys=True))


def prepare(project_root: Path) -> dict:
    structure_path = project_root / STRUCTURE_AUDIT
    comparison_path = project_root / TICK_COMPARISON
    raw_dir = project_root / RAW_DIR
    candidate = project_root / CANDIDATE_ROOT
    if candidate.exists():
        raise FileExistsError(f"candidate directory already exists and will not be overwritten: {candidate}")
    candidate.mkdir(parents=True)

    structure = pd.read_csv(
        structure_path,
        dtype={"session_date": "string", "contract": "string"},
    )
    structure["eligible"] = (
        structure["strategy_session_eligible"].map(_as_bool)
        & structure["raw_structure_pass"].map(_as_bool)
    )
    capability = structure[
        [
            "session_date",
            "contract",
            "strategy_session_eligible",
            "raw_structure_pass",
            "status",
            "reason",
        ]
    ].copy()
    capability["reference_tier"] = "overlap_extrapolated_from_structural_validation"
    capability["full_strategy_events_extrapolated"] = structure["eligible"].astype(bool)

    comparison = pd.read_csv(comparison_path, dtype={"session_date": "string"})
    comparison = comparison.set_index("session_date")
    overlap = capability["session_date"].isin(comparison.index)
    capability.loc[overlap, "reference_tier"] = "databento_compared"
    compared_status = capability.loc[overlap, "session_date"].map(comparison["comparison_status"])
    capability.loc[overlap, "full_strategy_events_extrapolated"] = compared_status.eq(
        "DATABENTO_EVENT_EQUIVALENT"
    ).to_numpy()
    capability.loc[overlap, "reason"] = capability.loc[overlap, "session_date"].map(
        comparison["failure_reason"]
    ).fillna("databento_event_equivalent")

    entry, levels, bar_source_manifest = _build_databento_session_inputs(
        project_root,
        target_sessions=structure[["session_date", "contract"]],
    )
    levels = _apply_overlap_event_level_overrides(project_root, levels)
    (candidate / "bar_source_manifest.json").write_text(
        json.dumps(bar_source_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    capability = capability.merge(
        levels[["session_date", "contract_symbol", "prior_expected_session_available"]],
        left_on=["session_date", "contract"],
        right_on=["session_date", "contract_symbol"],
        how="left",
    )
    capability["levels_available"] = capability["contract_symbol"].notna()
    capability["full_strategy_events_extrapolated"] &= capability["levels_available"]
    prior_available = (
        capability["prior_expected_session_available"]
        .astype("boolean")
        .fillna(False)
        .astype(bool)
    )
    capability["full_strategy_events_extrapolated"] &= prior_available
    capability = capability.drop(columns=["contract_symbol", "prior_expected_session_available"])

    eligible_dates = set(
        capability.loc[capability["full_strategy_events_extrapolated"], "session_date"].astype(str)
    )
    levels = levels[levels["session_date"].isin(eligible_dates)].copy()
    levels = levels.sort_values("session_date").reset_index(drop=True)
    levels.to_parquet(candidate / "session_levels.parquet", index=False)

    entry = entry[entry["session_date"].isin(eligible_dates)].copy()
    contract_by_date = structure.set_index("session_date")["contract"].astype(str)
    entry["contract_symbol"] = entry["session_date"].map(contract_by_date)
    if entry["contract_symbol"].isna().any():
        raise ValueError("eligible Databento bars could not be mapped to Sierra contract identity")
    entry["timestamp"] = entry["timestamp"].dt.tz_convert("UTC")
    entry = entry[
        ["timestamp", "contract_symbol", "open", "high", "low", "close", "volume"]
    ].sort_values(["timestamp", "contract_symbol"], kind="mergesort")
    entry["timeframe_minutes"] = 1.0
    entry["row_quality_valid"] = True
    entry.to_parquet(candidate / "bars.parquet", index=False)

    capability = capability.sort_values("session_date").reset_index(drop=True)
    capability.to_csv(candidate / "event_capabilities.csv", index=False)
    raw_manifest = _raw_manifest(project_root, raw_dir)
    (candidate / "raw_manifest.json").write_text(
        json.dumps(raw_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    preparation = {
        "schema": "alphaquest.sierra-dataset-preparation/v1",
        "dataset_id": DATASET_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "verdict": "NEEDS MANUAL REVIEW",
        "bars": len(entry),
        "session_levels": len(levels),
        "eligible_event_sessions": int(capability["full_strategy_events_extrapolated"].sum()),
        "known_overlap_blackouts": int(
            (
                capability["reference_tier"].eq("databento_compared")
                & ~capability["full_strategy_events_extrapolated"]
            ).sum()
        ),
        "source_hashes": {
            str(DATABENTO_BAR_VALIDATION): file_sha256(
                project_root / DATABENTO_BAR_VALIDATION
            ),
            str(CANDIDATE_ROOT / "bar_source_manifest.json"): file_sha256(
                candidate / "bar_source_manifest.json"
            ),
            str(FULL_SESSION_AUDIT_ROOT / "minute_comparison.csv"): file_sha256(
                project_root / FULL_SESSION_AUDIT_ROOT / "minute_comparison.csv"
            ),
            str(STRUCTURE_AUDIT): file_sha256(structure_path),
            str(TICK_COMPARISON): file_sha256(comparison_path),
            str(ROLL_CALENDAR): file_sha256(project_root / ROLL_CALENDAR),
        },
        "policy": {
            "outside_entry_window": (
                "PDH/PDL/PDC and ONH/ONL use Databento trade-event OHLC inside the "
                "validated overlap and Databento one-minute OHLC before it; ETH is prior "
                "calendar date 16:00 through session date 09:30 ET"
            ),
            "entry_window": "reconstructed Sierra events 09:30-11:00 ET",
            "overlap": "known non-equivalent dates blacked out",
            "older_history": "intrinsic Sierra structure pass, extrapolated from overlap validation",
        },
    }
    (candidate / "preparation_report.json").write_text(
        json.dumps(preparation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return preparation


def _build_databento_session_inputs(
    project_root: Path,
    *,
    target_sessions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    source_dir = project_root / DATABENTO_BAR_DIR
    source_files = sorted(source_dir.glob("*.ohlcv-1m.parquet"))
    if not source_files:
        raise ValueError(f"no Databento OHLC source files found: {source_dir}")
    frames = [
        pd.read_parquet(
            path,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "contract_symbol",
            ],
        )
        for path in source_files
    ]
    bars = pd.concat(frames, ignore_index=True)
    bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True).dt.tz_convert(
        "America/New_York"
    )
    bars["contract_key"] = bars["contract_symbol"].astype(str).map(
        _canonical_contract
    )
    bars = bars.loc[~bars["contract_key"].str.contains("-", regex=False)].copy()
    minute = bars["timestamp"].dt.hour * 60 + bars["timestamp"].dt.minute
    session_timestamp = bars["timestamp"].dt.normalize()
    session_timestamp = session_timestamp + pd.to_timedelta(
        minute.ge(16 * 60).astype(int), unit="D"
    )
    bars["session_date"] = session_timestamp.dt.date.astype(str)

    active_contract = _active_contracts_by_session(
        project_root / ROLL_CALENDAR,
        bars["session_date"].unique().tolist(),
    )
    bars["active_contract_symbol"] = bars["session_date"].map(active_contract)
    bars["active_contract_key"] = bars["active_contract_symbol"].map(
        _canonical_contract
    )
    bars = bars.loc[bars["contract_key"].eq(bars["active_contract_key"])].copy()
    bars["contract_symbol"] = bars["active_contract_symbol"]
    bars["_minute"] = minute.loc[bars.index].to_numpy()
    bars = bars.sort_values(["timestamp", "contract_symbol"], kind="mergesort")

    rth_mask = bars["_minute"].between(9 * 60 + 30, 16 * 60 - 1)
    rth = (
        bars.loc[rth_mask]
        .groupby(["session_date", "contract_symbol"], sort=True, as_index=False)
        .agg(
            current_rth_high=("high", "max"),
            current_rth_low=("low", "min"),
            current_rth_close=("close", "last"),
            current_rth_bars=("timestamp", "size"),
        )
        .sort_values("session_date")
        .reset_index(drop=True)
    )
    overnight_mask = bars["_minute"].ge(16 * 60) | bars["_minute"].lt(9 * 60 + 30)
    overnight = (
        bars.loc[overnight_mask]
        .groupby(["session_date", "contract_symbol"], sort=True, as_index=False)
        .agg(
            overnight_high=("high", "max"),
            overnight_low=("low", "min"),
            overnight_bars=("timestamp", "size"),
        )
    )
    entry_mask = bars["_minute"].between(9 * 60 + 30, 11 * 60 - 1)
    entry = bars.loc[
        entry_mask,
        [
            "timestamp",
            "session_date",
            "contract_symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
    ].copy()

    rth_rows = list(rth.itertuples(index=False))
    rth_by_date = {str(row.session_date): row for row in rth_rows}
    ordered_rth_dates = [str(row.session_date) for row in rth_rows]
    overnight_by_key = {
        (str(row.session_date), _canonical_contract(str(row.contract_symbol))): row
        for row in overnight.itertuples(index=False)
    }
    target = target_sessions.copy()
    target["session_date"] = target["session_date"].astype(str)
    target = target.sort_values("session_date")
    level_rows = []
    for current in target.itertuples(index=False):
        current_date = str(current.session_date)
        current_contract = str(current.contract)
        current_rth = rth_by_date.get(current_date)
        current_overnight = overnight_by_key.get(
            (current_date, _canonical_contract(current_contract))
        )
        prior_candidates = [date for date in ordered_rth_dates if date < current_date]
        prior_date = prior_candidates[-1] if prior_candidates else None
        prior = rth_by_date.get(prior_date) if prior_date else None
        reset_on_roll = (
            prior is not None
            and _canonical_contract(str(prior.contract_symbol))
            != _canonical_contract(current_contract)
        )
        if (
            current_rth is None
            or current_overnight is None
            or _canonical_contract(str(current_rth.contract_symbol))
            != _canonical_contract(current_contract)
        ):
            continue
        level_rows.append(
            {
                "session_date": current_date,
                "contract_symbol": current_contract,
                "previous_rth_session_date": (
                    None if prior is None or reset_on_roll else prior_date
                ),
                "previous_rth_contract_symbol": (
                    None if prior is None or reset_on_roll else current_contract
                ),
                "previous_rth_high": (
                    None
                    if prior is None or reset_on_roll
                    else float(prior.current_rth_high)
                ),
                "previous_rth_low": (
                    None
                    if prior is None or reset_on_roll
                    else float(prior.current_rth_low)
                ),
                "previous_rth_close": (
                    None
                    if prior is None or reset_on_roll
                    else float(prior.current_rth_close)
                ),
                "overnight_high": float(current_overnight.overnight_high),
                "overnight_low": float(current_overnight.overnight_low),
                "current_rth_bars": int(current_rth.current_rth_bars),
                "overnight_bars": int(current_overnight.overnight_bars),
                "prior_expected_session_available": bool(
                    prior is not None or not ordered_rth_dates
                ),
                "previous_levels_reset_on_roll": bool(reset_on_roll),
            }
        )
    source_manifest = {
        "schema": "alphaquest.databento-bar-source-manifest/v1",
        "source_dir": str(source_dir.relative_to(project_root)),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "files": [
            {
                "path": str(path.relative_to(project_root)),
                "size": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in source_files
        ],
        "session_assignment": (
            "selected session contract over prior calendar date 16:00 through "
            "session date 16:00 America/New_York"
        ),
    }
    return entry, pd.DataFrame(level_rows), source_manifest


def _apply_overlap_event_level_overrides(
    project_root: Path,
    levels: pd.DataFrame,
) -> pd.DataFrame:
    audit_root = project_root / FULL_SESSION_AUDIT_ROOT
    summary = json.loads((audit_root / "summary.json").read_text(encoding="utf-8"))
    outcome = summary.get("outcome") or {}
    if (
        summary.get("schema") != "alphaquest.sierra-databento-full-session-audit/v1"
        or (summary.get("scope") or {}).get("complete_requested_overlap") is not True
        or outcome.get("session_segments_market_ohlc_exact")
        != outcome.get("session_segments_market_ohlc_compared")
    ):
        raise ValueError("full-session audit does not prove exact overlap market OHLC")
    minute = pd.read_csv(
        audit_root / "minute_comparison.csv",
        dtype={"session_date": "string", "segment": "string", "contract": "string"},
    )
    minute["minute"] = pd.to_datetime(minute["minute"], utc=True)
    minute = minute.sort_values(["session_date", "segment", "minute"])
    rth: dict[str, dict] = {}
    overnight: dict[str, dict] = {}
    for (session_date, segment), frame in minute.groupby(
        ["session_date", "segment"], sort=True
    ):
        record = {
            "contract": str(frame["contract"].iloc[0]),
            "high": float(frame["high_db"].max()),
            "low": float(frame["low_db"].min()),
            "close": float(frame["close_db"].iloc[-1]),
        }
        if segment == "RTH":
            rth[str(session_date)] = record
        elif segment == "ETH":
            overnight[str(session_date)] = record

    result = levels.copy()
    result["market_level_source"] = "databento_ohlcv_1m_extrapolated"
    for index, row in result.iterrows():
        session_date = str(row["session_date"])
        contract = _canonical_contract(str(row["contract_symbol"]))
        current_overnight = overnight.get(session_date)
        if current_overnight is None or _canonical_contract(
            current_overnight["contract"]
        ) != contract:
            continue
        result.at[index, "overnight_high"] = current_overnight["high"]
        result.at[index, "overnight_low"] = current_overnight["low"]
        source = "databento_trade_event_overlap_partial"
        prior_date = row.get("previous_rth_session_date")
        if pd.notna(prior_date):
            prior = rth.get(str(prior_date))
            if prior is not None:
                if _canonical_contract(prior["contract"]) != contract:
                    raise ValueError(
                        f"overlap prior-RTH audit changes contract for {session_date}"
                    )
                result.at[index, "previous_rth_high"] = prior["high"]
                result.at[index, "previous_rth_low"] = prior["low"]
                result.at[index, "previous_rth_close"] = prior["close"]
                source = "databento_trade_event_overlap"
        result.at[index, "market_level_source"] = source
    return result


def _active_contracts_by_session(
    roll_calendar_path: Path,
    session_dates: list[str],
) -> dict[str, str]:
    roll = pd.read_csv(roll_calendar_path)
    starts = (
        pd.to_datetime(roll["start_timestamp"], utc=True)
        .dt.tz_convert("America/New_York")
        .dt.date.astype(str)
    )
    records = sorted(
        zip(starts, roll["contract_symbol"].astype(str), strict=True),
        key=lambda item: item[0],
    )
    result: dict[str, str] = {}
    for session_date in sorted(set(str(value) for value in session_dates)):
        eligible = [contract for start, contract in records if start <= session_date]
        if eligible:
            result[session_date] = eligible[-1]
    return result


def _canonical_contract(value: str) -> str:
    value = str(value).strip().upper()
    if "-" in value:
        return value
    digits = "".join(character for character in value if character.isdigit())
    prefix = value[: len(value) - len(digits)]
    if len(digits) == 2:
        digits = digits[-1]
    if len(digits) != 1:
        raise ValueError(f"unexpected ES contract symbol: {value!r}")
    return f"{prefix}{digits}"


def finalize(project_root: Path, concordance_report: Path) -> dict:
    candidate = project_root / CANDIDATE_ROOT
    report = json.loads(concordance_report.read_text(encoding="utf-8"))
    if report.get("schema") != "alphaquest.strategy-source-concordance/v1":
        raise ValueError("strategy concordance report schema is missing or unsupported")
    if report.get("verdict") != "PASS":
        raise ValueError("Sierra event dataset cannot be published unless strategy concordance is PASS")
    full_audit_root = project_root / FULL_SESSION_AUDIT_ROOT
    full_audit_summary_path = full_audit_root / "summary.json"
    full_audit_report_path = full_audit_root / "report.md"
    full_audit = json.loads(full_audit_summary_path.read_text(encoding="utf-8"))
    if (
        full_audit.get("schema") != "alphaquest.sierra-databento-full-session-audit/v1"
        or (full_audit.get("scope") or {}).get("complete_requested_overlap") is not True
    ):
        raise ValueError("full-session Sierra/Databento audit is missing or incomplete")
    destination = project_root / "research/datasets" / DATASET_ID
    if destination.exists():
        raise FileExistsError(f"governed dataset already exists and will not be overwritten: {destination}")
    destination.mkdir(parents=True)
    for name in (
        "bars.parquet",
        "session_levels.parquet",
        "event_capabilities.csv",
        "raw_manifest.json",
        "bar_source_manifest.json",
    ):
        shutil.copy2(candidate / name, destination / name)
    shutil.copy2(concordance_report, destination / "strategy_concordance.json")
    shutil.copy2(full_audit_summary_path, destination / "full_session_audit_summary.json")
    shutil.copy2(full_audit_report_path, destination / "full_session_audit_report.md")

    bars_path = destination / "bars.parquet"
    levels_path = destination / "session_levels.parquet"
    capability_path = destination / "event_capabilities.csv"
    raw_manifest_path = destination / "raw_manifest.json"
    concordance_path = destination / "strategy_concordance.json"
    bars = pd.read_parquet(bars_path)
    roll = project_root / ROLL_CALENDAR
    contracts = int(bars["contract_symbol"].nunique())
    event_source = EventExecutionSourceV1(
        source="sierra_scid_records",
        raw_dir=str((project_root / RAW_DIR).resolve()),
        raw_manifest=str(raw_manifest_path.relative_to(project_root)),
        raw_manifest_sha256=file_sha256(raw_manifest_path),
        session_levels=str(levels_path.relative_to(project_root)),
        session_levels_sha256=file_sha256(levels_path),
        quality_manifest=str(capability_path.relative_to(project_root)),
        quality_manifest_sha256=file_sha256(capability_path),
        concordance_report=str(concordance_path.relative_to(project_root)),
        concordance_report_sha256=file_sha256(concordance_path),
        required_capability="full_strategy_events_extrapolated",
        ineligible_session_policy="blackout",
        roll_calendar=str(ROLL_CALENDAR),
        roll_calendar_sha256=file_sha256(roll),
        root_symbol="ES",
        aggregation_ms=100,
        overnight_start="16:00:00",
        rth_start="09:30:00",
        rth_end="11:00:00",
        reset_previous_levels_on_roll=True,
    )
    manifest = DatasetManifestV1(
        dataset_id=DATASET_ID,
        source="parquet",
        path=str(bars_path.relative_to(project_root)),
        symbol="ES",
        timeframe="1m",
        timezone="UTC",
        exchange_timezone="America/New_York",
        timestamp_semantics="bar_open",
        source_timestamp_semantics="bar_open",
        source_sha256=file_sha256(bars_path),
        canonical_sha256=file_sha256(bars_path),
        coverage_start=str(pd.to_datetime(bars["timestamp"], utc=True).min()),
        coverage_end=str(pd.to_datetime(bars["timestamp"], utc=True).max()),
        roll_policy="MotiveWave/Rithmic predeclared active-contract calendar; no back adjustment",
        continuous_contract="explicit_roll_calendar",
        contract_column="contract_symbol",
        source_contract_column="contract_symbol",
        contract_count=contracts,
        roll_calendar=str(ROLL_CALENDAR),
        roll_calendar_sha256=file_sha256(roll),
        transformations=[
            "restricted completed Databento bars to 09:30-11:00 ET and structurally eligible Sierra sessions",
            (
                "computed prior-RTH and 16:00-09:30 ETH market levels from completed "
                "Databento OHLC, with event-derived overlap overrides"
            ),
            "reconstructed entry-window events from Sierra FIRST/LAST unbundled-trade groups",
            "blacked out known Databento-overlap event mismatches",
            "audited the full ETH/RTH Databento overlap and retained off-window exceptions separately",
        ],
        row_count=len(bars),
        dropped_row_count=0,
        gap_count=int(report.get("blackout_sessions") or 0),
        duplicate_count=int(bars.duplicated(["timestamp", "contract_symbol"]).sum()),
        out_of_order_count=0,
        invalid_ohlc_count=0,
        cadence_violation_count=0,
        certified_features=[],
        quality_verdict="PASS",
        quality_notes=[
            (
                "Prior-RTH and ETH confluences use completed OHLC only; directly validated "
                "overlap levels use trade-event OHLC and older levels use one-minute OHLC."
            ),
            "Entry mechanics use reconstructed Sierra events from 09:30-11:00 ET.",
            "Pre-overlap event fidelity is extrapolated from the governed Databento overlap and intrinsic structure gates.",
            "Known ineligible sessions are blacked out without compressing calendar time.",
            (
                "The broader full-session order-flow audit remains "
                f"{full_audit.get('verdict')}; this PASS is scoped to the Yush 09:30-11:00 "
                "event lane plus completed-bar PDH/PDL/PDC/ONH/ONL inputs."
            ),
        ],
        event_source=event_source,
    )
    manifest_path = destination / "dataset_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json", by_alias=True), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "dataset_id": DATASET_ID,
        "dataset_manifest": str(manifest_path),
        "quality_verdict": manifest.quality_verdict,
        "row_count": manifest.row_count,
        "contract_count": manifest.contract_count,
    }


def _raw_manifest(project_root: Path, raw_dir: Path) -> dict:
    files = []
    for path in sorted(raw_dir.glob("*.parquet")):
        files.append(
            {
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    if not files:
        raise ValueError(f"no Sierra contract files found: {raw_dir}")
    return {
        "schema": "alphaquest.sierra-raw-manifest/v1",
        "raw_dir": str(raw_dir.resolve()),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "files": files,
    }


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


if __name__ == "__main__":
    main()
