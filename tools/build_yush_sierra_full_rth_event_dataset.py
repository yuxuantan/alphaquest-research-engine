"""Build the immutable full-RTH Sierra event dataset used by Yush v02.

The completed one-minute bars establish regular-session completeness. Exact
entry sequencing is still reconstructed from hash-bound Sierra SCID records and
is revalidated per session by the execution loader. Modern overlap sessions
must also pass the exhaustive full-session Databento comparison; older sessions
remain explicitly labelled as an extrapolation and retain the intrinsic
structure and runtime reconstruction gates.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil

import pandas as pd
import yaml

from alphaquest.authoring.models import DatasetManifestV1, EventExecutionSourceV1
from alphaquest.strategy_certification import get_strategy_certification
from alphaquest.utils.hashing import file_sha256
from build_yush_sierra_event_dataset import (
    DATABENTO_BAR_VALIDATION,
    FULL_SESSION_AUDIT_ROOT,
    RAW_DIR,
    ROLL_CALENDAR,
    STRUCTURE_AUDIT,
    _apply_overlap_event_level_overrides,
    _as_bool,
    _build_databento_session_inputs,
    _canonical_contract,
    _raw_manifest,
    _timestamp_repair_eligible,
)


DATASET_ID = "es_sierra_yush_events_20110815_20260529_full_rth_ny_inv02"
CANDIDATE_ROOT = Path(
    "data/reports/data_quality/ES/yush_sierra_full_rth_event_dataset_candidate_v1"
)
FULL_RTH_BARS = Path(
    "data/cache/orderflow/"
    "es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
)
FULL_RTH_BAR_VALIDATION = FULL_RTH_BARS.with_suffix(".validation.json")
ATR_SOURCE = Path(
    "research/datasets/"
    "es_sierra_yush_events_20110815_20260529_0930_1100_ny_inv02/"
    "atr14_3m_eth_context.parquet"
)
PARENT_CONFIG = Path(
    "research/campaigns/active/yush_orderflow_range/follow_up_attempts/"
    "pre_pnl_parameter_declaration_20260727t062734_a9fca5b1/v02/config.yaml"
)
MAX_GOVERNED_TIMESTAMP_INVERSION_RATE = 0.002


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--prepare-concordance-config", action="store_true")
    mode.add_argument("--finalize", action="store_true")
    parser.add_argument("--concordance-report", type=Path)
    parser.add_argument(
        "--max-timestamp-inversion-rate",
        type=float,
        default=MAX_GOVERNED_TIMESTAMP_INVERSION_RATE,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.project_root.resolve()
    if args.prepare:
        result = prepare(
            root,
            max_timestamp_inversion_rate=args.max_timestamp_inversion_rate,
        )
    elif args.prepare_concordance_config:
        result = prepare_concordance_config(root)
    else:
        if args.concordance_report is None:
            raise SystemExit("--finalize requires --concordance-report")
        report = (
            args.concordance_report
            if args.concordance_report.is_absolute()
            else root / args.concordance_report
        )
        result = finalize(
            root,
            report,
            max_timestamp_inversion_rate=args.max_timestamp_inversion_rate,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


def prepare_concordance_config(project_root: Path) -> dict:
    candidate = project_root / CANDIDATE_ROOT
    certification = get_strategy_certification(
        "yush_adaptive_orderflow_range",
        project_root,
        require_current=True,
    )
    output = (
        candidate
        / f"concordance_config_v{certification.implementation_version}.yaml"
    )
    if output.exists():
        raise FileExistsError(
            f"concordance config already exists and will not be overwritten: {output}"
        )
    config = yaml.safe_load(
        (project_root / PARENT_CONFIG).read_text(encoding="utf-8")
    )
    defaults = {
        name: parameter.default
        for name, parameter in certification.parameters.items()
    }
    config["strategy"]["event"]["params"] = dict(defaults)
    config["strategy"]["entry"]["params"]["mechanics"] = dict(defaults)
    config["strategy"]["flatten_time"] = "15:55:00"
    config["core"]["flatten_time"] = "15:55:00"
    config["core"]["latest_entry_time"] = "15:54:59"
    config["core"]["max_trades_per_day"] = 0
    config["apex_rules"]["force_flatten_time"] = "15:55:00"
    config["apex_rules"]["latest_flat_time"] = "15:55:00"
    config["apex_rules"]["latest_entry_time"] = "15:54:59"
    config["strategy_certification"] = {
        "strategy_id": certification.strategy_id,
        "implementation_version": certification.implementation_version,
        "implementation_sha256": certification.implementation_sha256,
        "manifest_sha256": certification.manifest_sha256,
    }
    output.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return {
        "config": str(output.relative_to(project_root)),
        "strategy_id": certification.strategy_id,
        "implementation_version": certification.implementation_version,
        "implementation_sha256": certification.implementation_sha256,
    }


def prepare(
    project_root: Path,
    *,
    max_timestamp_inversion_rate: float,
) -> dict:
    if not 0.0 <= max_timestamp_inversion_rate <= MAX_GOVERNED_TIMESTAMP_INVERSION_RATE:
        raise ValueError("max timestamp inversion rate must be between 0 and 0.002")
    candidate = project_root / CANDIDATE_ROOT
    if candidate.exists():
        raise FileExistsError(
            f"candidate directory already exists and will not be overwritten: {candidate}"
        )
    candidate.mkdir(parents=True)

    structure = pd.read_csv(
        project_root / STRUCTURE_AUDIT,
        dtype={"session_date": "string", "contract": "string"},
    )
    structure["timestamp_inversion_rate"] = (
        pd.to_numeric(
            structure["timestamp_inversions_in_source_order"],
            errors="raise",
        )
        / pd.to_numeric(structure["row_count"], errors="raise").clip(lower=1)
    )
    structure["timestamp_repair_eligible"] = structure.apply(
        lambda row: _timestamp_repair_eligible(
            row,
            max_timestamp_inversion_rate=max_timestamp_inversion_rate,
        ),
        axis=1,
    )
    structure["intrinsic_event_eligible"] = structure[
        "strategy_session_eligible"
    ].map(_as_bool) & (
        structure["raw_structure_pass"].map(_as_bool)
        | structure["timestamp_repair_eligible"]
    )

    bars = pd.read_parquet(project_root / FULL_RTH_BARS)
    bars["timestamp"] = pd.to_datetime(bars["timestamp"], errors="raise")
    bars["session_date"] = bars["timestamp"].dt.date.astype(str)
    bars = bars.loc[
        bars["session_date"].between("2011-08-15", "2026-05-29")
    ].copy()
    complete_sessions = set(bars["session_date"].astype(str))

    capability = structure[
        [
            "session_date",
            "contract",
            "strategy_session_eligible",
            "raw_structure_pass",
            "timestamp_inversions_in_source_order",
            "timestamp_inversion_rate",
            "timestamp_repair_eligible",
            "status",
            "reason",
        ]
    ].copy()
    capability["full_rth_bar_complete"] = capability["session_date"].isin(
        complete_sessions
    )
    capability["reference_tier"] = (
        "full_rth_extrapolated_from_intrinsic_and_completed_bar_validation"
    )
    capability["full_rth_strategy_events_extrapolated"] = (
        structure["intrinsic_event_eligible"]
        & capability["full_rth_bar_complete"]
    )

    overlap = pd.read_csv(
        project_root / FULL_SESSION_AUDIT_ROOT / "by_session.csv",
        dtype={"session_date": "string"},
    )
    overlap = overlap.dropna(subset=["session_date"]).set_index("session_date")
    compared_mask = capability["session_date"].isin(overlap.index)
    capability.loc[compared_mask, "reference_tier"] = (
        "databento_full_rth_compared"
    )
    overlap_status = capability.loc[compared_mask, "session_date"].map(
        overlap["rth_status"]
    )
    capability.loc[
        compared_mask,
        "full_rth_strategy_events_extrapolated",
    ] = overlap_status.eq("DATABENTO_EVENT_EQUIVALENT").to_numpy()
    capability.loc[compared_mask, "reason"] = capability.loc[
        compared_mask,
        "session_date",
    ].map(overlap["failure_reason"]).fillna("databento_full_rth_event_equivalent")

    _, levels, databento_manifest = _build_databento_session_inputs(
        project_root,
        target_sessions=structure[["session_date", "contract"]],
    )
    levels = _apply_overlap_event_level_overrides(project_root, levels)
    capability = capability.merge(
        levels[
            [
                "session_date",
                "contract_symbol",
                "prior_expected_session_available",
            ]
        ],
        left_on=["session_date", "contract"],
        right_on=["session_date", "contract_symbol"],
        how="left",
    )
    capability["levels_available"] = capability["contract_symbol"].notna()
    capability["full_rth_strategy_events_extrapolated"] &= capability[
        "levels_available"
    ]
    capability["full_rth_strategy_events_extrapolated"] &= (
        capability["prior_expected_session_available"]
        .astype("boolean")
        .fillna(False)
        .astype(bool)
    )
    capability = capability.drop(
        columns=["contract_symbol", "prior_expected_session_available"]
    )
    eligible_dates = set(
        capability.loc[
            capability["full_rth_strategy_events_extrapolated"],
            "session_date",
        ].astype(str)
    )

    levels = levels.loc[levels["session_date"].isin(eligible_dates)].copy()
    levels.sort_values("session_date").to_parquet(
        candidate / "session_levels.parquet",
        index=False,
    )

    contract_by_date = structure.set_index("session_date")["contract"].astype(str)
    bars = bars.loc[bars["session_date"].isin(eligible_dates)].copy()
    bars["expected_contract"] = bars["session_date"].map(contract_by_date)
    contract_match = [
        _canonical_contract(actual) == _canonical_contract(expected)
        for actual, expected in zip(
            bars["contract_symbol"].astype(str),
            bars["expected_contract"].astype(str),
            strict=True,
        )
    ]
    if not all(contract_match):
        raise ValueError("full-RTH bar cache does not match the governed roll calendar")
    bars["timestamp"] = (
        bars["timestamp"]
        .dt.tz_localize("America/New_York", ambiguous="raise", nonexistent="raise")
        .dt.tz_convert("UTC")
    )
    bars = bars[
        ["timestamp", "contract_symbol", "open", "high", "low", "close", "volume"]
    ].sort_values(["timestamp", "contract_symbol"], kind="mergesort")
    bars["timeframe_minutes"] = 1.0
    bars["row_quality_valid"] = True
    bars.to_parquet(candidate / "bars.parquet", index=False)

    capability.sort_values("session_date").to_csv(
        candidate / "event_capabilities.csv",
        index=False,
    )
    (candidate / "raw_manifest.json").write_text(
        json.dumps(
            _raw_manifest(project_root, project_root / RAW_DIR),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    bar_sources = {
        "schema": "alphaquest.full-rth-bar-source-manifest/v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "full_rth_bars": str(FULL_RTH_BARS),
        "full_rth_bars_sha256": file_sha256(project_root / FULL_RTH_BARS),
        "full_rth_validation": str(FULL_RTH_BAR_VALIDATION),
        "full_rth_validation_sha256": file_sha256(
            project_root / FULL_RTH_BAR_VALIDATION
        ),
        "market_level_sources": databento_manifest,
    }
    (candidate / "bar_source_manifest.json").write_text(
        json.dumps(bar_sources, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema": "alphaquest.sierra-dataset-preparation/v1",
        "dataset_id": DATASET_ID,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "verdict": "NEEDS MANUAL REVIEW",
        "bars": len(bars),
        "eligible_event_sessions": len(eligible_dates),
        "known_overlap_blackouts": int(
            (
                capability["reference_tier"].eq("databento_full_rth_compared")
                & ~capability["full_rth_strategy_events_extrapolated"]
            ).sum()
        ),
        "policy": {
            "entry_window": "reconstructed Sierra events 09:30-16:00 ET",
            "required_capability": "full_rth_strategy_events_extrapolated",
            "full_rth_completeness": str(FULL_RTH_BAR_VALIDATION),
            "modern_overlap": "all non-equivalent RTH sessions are blacked out",
            "older_history": (
                "intrinsic Sierra morning structure plus complete full-RTH bars; "
                "full-session reconstruction remains fail-closed at runtime"
            ),
            "max_timestamp_inversion_rate": max_timestamp_inversion_rate,
        },
    }
    (candidate / "preparation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def finalize(
    project_root: Path,
    concordance_report: Path,
    *,
    max_timestamp_inversion_rate: float,
) -> dict:
    report = json.loads(concordance_report.read_text(encoding="utf-8"))
    if (
        report.get("schema") != "alphaquest.strategy-source-concordance/v1"
        or report.get("verdict") != "PASS"
        or (report.get("scope") or {}).get("rth_end") != "16:00:00"
    ):
        raise ValueError(
            "full-RTH dataset requires a PASS strategy concordance through 16:00"
        )
    candidate = project_root / CANDIDATE_ROOT
    destination = project_root / "research/datasets" / DATASET_ID
    if destination.exists():
        raise FileExistsError(
            f"governed dataset already exists and will not be overwritten: {destination}"
        )
    destination.mkdir(parents=True)
    for name in (
        "bars.parquet",
        "session_levels.parquet",
        "event_capabilities.csv",
        "raw_manifest.json",
        "bar_source_manifest.json",
        "preparation_report.json",
    ):
        shutil.copy2(candidate / name, destination / name)
    shutil.copy2(concordance_report, destination / "strategy_concordance.json")
    shutil.copy2(project_root / ATR_SOURCE, destination / ATR_SOURCE.name)
    for name in ("summary.json", "report.md", "by_session.csv"):
        shutil.copy2(
            project_root / FULL_SESSION_AUDIT_ROOT / name,
            destination / f"full_session_audit_{name}",
        )

    bars_path = destination / "bars.parquet"
    levels_path = destination / "session_levels.parquet"
    capability_path = destination / "event_capabilities.csv"
    raw_manifest_path = destination / "raw_manifest.json"
    concordance_path = destination / "strategy_concordance.json"
    bars = pd.read_parquet(bars_path)
    roll = project_root / ROLL_CALENDAR
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
        required_capability="full_rth_strategy_events_extrapolated",
        ineligible_session_policy="blackout",
        timestamp_inversion_policy="preserve_source_order_clamp",
        max_timestamp_inversion_rate=max_timestamp_inversion_rate,
        roll_calendar=str(ROLL_CALENDAR),
        roll_calendar_sha256=file_sha256(roll),
        root_symbol="ES",
        aggregation_ms=100,
        overnight_start="16:00:00",
        rth_start="09:30:00",
        rth_end="16:00:00",
        reset_previous_levels_on_roll=True,
    )
    capability = pd.read_csv(capability_path)
    blackouts = int(
        (~capability["full_rth_strategy_events_extrapolated"].map(_as_bool)).sum()
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
        roll_policy=(
            "MotiveWave/Rithmic predeclared active-contract calendar; "
            "no back adjustment"
        ),
        continuous_contract="explicit_roll_calendar",
        contract_column="contract_symbol",
        source_contract_column="contract_symbol",
        contract_count=int(bars["contract_symbol"].nunique()),
        roll_calendar=str(ROLL_CALENDAR),
        roll_calendar_sha256=file_sha256(roll),
        transformations=[
            "restricted completed Sierra bars to regular 09:30-16:00 ET sessions",
            "reconstructed full-RTH events from Sierra FIRST/LAST trade groups",
            "blacked out all known non-equivalent full-RTH overlap sessions",
            "retained per-session runtime structure and timestamp fail-closed gates",
        ],
        row_count=len(bars),
        dropped_row_count=0,
        gap_count=blackouts,
        duplicate_count=int(
            bars.duplicated(["timestamp", "contract_symbol"]).sum()
        ),
        out_of_order_count=0,
        invalid_ohlc_count=0,
        cadence_violation_count=0,
        certified_features=[],
        quality_verdict="PASS",
        quality_notes=[
            "Entry events cover 09:30-16:00 ET; the strategy blocks new entries after 15:54:59 and flattens at 15:55.",
            "Modern non-equivalent full-RTH overlap sessions are blacked out.",
            "Older event fidelity is an explicit extrapolation; reconstruction remains fail-closed per session.",
        ],
        event_source=event_source,
    )
    manifest_path = destination / "dataset_manifest.json"
    manifest_path.write_text(
        json.dumps(
            manifest.model_dump(mode="json", by_alias=True),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "dataset_id": DATASET_ID,
        "dataset_manifest": str(manifest_path),
        "quality_verdict": manifest.quality_verdict,
        "row_count": manifest.row_count,
        "contract_count": manifest.contract_count,
        "blackout_sessions": blackouts,
    }


if __name__ == "__main__":
    main()
