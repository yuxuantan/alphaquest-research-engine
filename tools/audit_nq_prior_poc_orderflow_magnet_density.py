from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

import pandas as pd

from alphaquest.data.pipeline import prepare_data
from alphaquest.strategy_modules.entry.prior_poc_orderflow_magnet import PriorPocOrderflowMagnetEntry


CAMPAIGN_ID = "nq_prior_poc_orderflow_magnet"
AUDIT_DATE = "2026-06-30"
ARTIFACT_STAMP = "20260630"
ARTIFACT_ROOT = Path("research_artifacts")
LIMITED_START = pd.Timestamp("2011-02-22").date()
LIMITED_END = pd.Timestamp("2012-09-07").date()
MIN_FULL_SIGNALS_PER_YEAR = 50.0
MIN_LIMITED_SIGNALS_PER_YEAR = 50.0
MIN_LATEST_252_SIGNALS = 50

VARIANTS = [
    {
        "variant_id": "morning_above_poc_signed_magnet_short",
        "setup_mode": "above_poc_magnet_short",
        "start_time": "09:35:00",
        "end_time": "11:30:00",
        "flow_mode": "signed_volume",
        "allow_long": False,
        "allow_short": True,
    },
    {
        "variant_id": "morning_below_poc_signed_magnet_long",
        "setup_mode": "below_poc_magnet_long",
        "start_time": "09:35:00",
        "end_time": "11:30:00",
        "flow_mode": "signed_volume",
        "allow_long": True,
        "allow_short": False,
    },
    {
        "variant_id": "late_morning_large10_two_sided_magnet",
        "setup_mode": "two_sided_magnet",
        "start_time": "10:30:00",
        "end_time": "12:30:00",
        "flow_mode": "large10",
        "allow_long": True,
        "allow_short": True,
    },
    {
        "variant_id": "midday_signed_two_sided_magnet",
        "setup_mode": "two_sided_magnet",
        "start_time": "12:00:00",
        "end_time": "14:00:00",
        "flow_mode": "signed_volume",
        "allow_long": True,
        "allow_short": True,
    },
    {
        "variant_id": "afternoon_large20_two_sided_magnet",
        "setup_mode": "two_sided_magnet",
        "start_time": "13:30:00",
        "end_time": "15:30:00",
        "flow_mode": "large20",
        "allow_long": True,
        "allow_short": True,
    },
]

ENTRY_GRID = {
    "min_poc_distance_ticks": [4, 8, 12],
    "min_orderflow_imbalance": [0.0, 0.02, 0.04],
}


def main() -> None:
    data, quality = prepare_data(_data_config(), subset_config=_subset(), timeframe="5m")
    data = data.sort_values("timestamp").reset_index(drop=True)
    data["session_date"] = pd.to_datetime(data["session_date"]).dt.date
    sessions = sorted(data["session_date"].dropna().unique())
    latest_sessions = set(sessions[-252:])
    records = data.to_dict(orient="records")

    rows = []
    for variant in VARIANTS:
        for min_poc_distance_ticks, min_orderflow_imbalance in itertools.product(
            ENTRY_GRID["min_poc_distance_ticks"],
            ENTRY_GRID["min_orderflow_imbalance"],
        ):
            params = _entry_params(
                variant,
                min_poc_distance_ticks=min_poc_distance_ticks,
                min_orderflow_imbalance=min_orderflow_imbalance,
            )
            signal_dates = _signal_dates(records, params)
            full_count = len(signal_dates)
            limited_count = sum(LIMITED_START <= day <= LIMITED_END for day in signal_dates)
            latest_count = sum(day in latest_sessions for day in signal_dates)
            full_per_year = _per_year(full_count, sessions[0], sessions[-1])
            limited_per_year = _per_year(limited_count, LIMITED_START, LIMITED_END)
            pass_gate = (
                full_per_year >= MIN_FULL_SIGNALS_PER_YEAR
                and limited_per_year >= MIN_LIMITED_SIGNALS_PER_YEAR
                and latest_count >= MIN_LATEST_252_SIGNALS
            )
            rows.append(
                {
                    "campaign_id": CAMPAIGN_ID,
                    "variant_id": variant["variant_id"],
                    "setup_mode": variant["setup_mode"],
                    "flow_mode": variant["flow_mode"],
                    "start_time": variant["start_time"],
                    "end_time": variant["end_time"],
                    "min_poc_distance_ticks": min_poc_distance_ticks,
                    "min_orderflow_imbalance": min_orderflow_imbalance,
                    "full_start_date": str(sessions[0]),
                    "full_end_date": str(sessions[-1]),
                    "full_signals": full_count,
                    "full_signals_per_year": full_per_year,
                    "limited_start_date": str(LIMITED_START),
                    "limited_end_date": str(LIMITED_END),
                    "limited_signals": limited_count,
                    "limited_signals_per_year": limited_per_year,
                    "latest_252_start_date": str(sessions[-252]),
                    "latest_252_end_date": str(sessions[-1]),
                    "latest_252_signals": latest_count,
                    "density_gate_pass": pass_gate,
                }
            )

    detail = pd.DataFrame(rows)
    summary = _summary(detail)
    machine_summary = _machine_summary(detail, summary, sessions, quality)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    detail_path = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.csv"
    summary_path = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_summary_{ARTIFACT_STAMP}.csv"
    markdown_path = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.md"
    detail.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)
    markdown_path.write_text(_markdown(summary, machine_summary, detail_path, summary_path), encoding="utf-8")
    print(json.dumps(machine_summary, indent=2, sort_keys=True))


def _data_config() -> dict:
    return {
        "dataset_id": "nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny",
        "source_timeframe": "1m",
        "source": "parquet",
        "raw_parquet": "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet",
        "symbol": "NQ",
        "timezone": "America/New_York",
        "exchange_timezone": "America/New_York",
        "feature_set": "none",
        "warmup_days": 0,
        "rth_start": "09:30:00",
        "rth_end": "15:59:00",
    }


def _subset() -> dict:
    return {
        "start_date": "2011-01-03",
        "end_date": "2026-06-12",
        "session_labels": ["RTH"],
    }


def _entry_params(
    variant: dict,
    *,
    min_poc_distance_ticks: int,
    min_orderflow_imbalance: float,
) -> dict:
    params = copy.deepcopy(variant)
    params.update(
        {
            "flatten_time": "15:55:00",
            "bar_interval_minutes": 5,
            "tick_size": 0.25,
            "value_area_fraction": 0.7,
            "poc_buffer_ticks": 1,
            "min_poc_distance_ticks": min_poc_distance_ticks,
            "max_poc_distance_ticks": 160,
            "min_toward_move_ticks": 1,
            "require_open_same_side": True,
            "min_orderflow_imbalance": min_orderflow_imbalance,
            "min_prior_profile_bars": 50,
            "max_trades_per_day": 1,
        }
    )
    params.pop("variant_id")
    return params


def _signal_dates(records: list[dict], params: dict) -> list:
    entry = PriorPocOrderflowMagnetEntry(params)
    dates = []
    for bar in records:
        signal = entry.on_bar_close(bar, trades_today=0)
        if signal is not None:
            dates.append(bar["session_date"])
    return dates


def _summary(detail: pd.DataFrame) -> pd.DataFrame:
    return (
        detail.groupby("variant_id", as_index=False)
        .agg(
            rows=("density_gate_pass", "size"),
            passing_rows=("density_gate_pass", "sum"),
            min_full_signals_per_year=("full_signals_per_year", "min"),
            max_full_signals_per_year=("full_signals_per_year", "max"),
            min_limited_signals_per_year=("limited_signals_per_year", "min"),
            max_limited_signals_per_year=("limited_signals_per_year", "max"),
            min_latest_252_signals=("latest_252_signals", "min"),
            max_latest_252_signals=("latest_252_signals", "max"),
        )
        .assign(variant_density_gate_pass=lambda df: df["passing_rows"].eq(df["rows"]))
    )


def _machine_summary(detail: pd.DataFrame, summary: pd.DataFrame, sessions: list, quality: dict) -> dict:
    passing_rows = int(detail["density_gate_pass"].sum())
    total_rows = int(len(detail))
    passing_variants = int(summary["variant_density_gate_pass"].sum())
    return {
        "audit_date": AUDIT_DATE,
        "campaign_id": CAMPAIGN_ID,
        "data_quality": quality,
        "decision": "approve_for_testing" if passing_variants == len(VARIANTS) else "reject_before_pnl",
        "full_start_date": str(sessions[0]),
        "full_end_date": str(sessions[-1]),
        "latest_252_start_date": str(sessions[-252]),
        "latest_252_end_date": str(sessions[-1]),
        "limited_start_date": str(LIMITED_START),
        "limited_end_date": str(LIMITED_END),
        "min_full_signals_per_year_required": MIN_FULL_SIGNALS_PER_YEAR,
        "min_limited_signals_per_year_required": MIN_LIMITED_SIGNALS_PER_YEAR,
        "min_latest_252_signals_required": MIN_LATEST_252_SIGNALS,
        "passing_rows": passing_rows,
        "passing_variants": passing_variants,
        "total_rows": total_rows,
        "total_variants": len(VARIANTS),
        "variant_summary": summary.to_dict(orient="records"),
    }


def _markdown(summary: pd.DataFrame, machine_summary: dict, detail_path: Path, summary_path: Path) -> str:
    lines = [
        f"# {CAMPAIGN_ID} Density Audit",
        "",
        f"Audit date: {AUDIT_DATE}.",
        "",
        "Decision: "
        + ("APPROVE FOR TESTING" if machine_summary["decision"] == "approve_for_testing" else "REJECT BEFORE PNL"),
        "",
        "This pre-PnL density audit uses the repository `PriorPocOrderflowMagnetEntry` module on completed 5-minute NQ RTH bars. The prior POC is built only after the previous RTH session is complete, and signals are counted on completed bar close before next-bar entry.",
        "",
        f"Detail CSV: `{detail_path}`",
        f"Summary CSV: `{summary_path}`",
        "",
        _markdown_table(summary),
        "",
        "Gate: every declared entry row must clear 50 signals/year over full history, 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions.",
        "",
    ]
    return "\n".join(lines)


def _per_year(count: int, start, end) -> float:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    days = max((end_ts - start_ts).days + 1, 1)
    return float(count) / (days / 365.25)


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for record in frame.to_dict(orient="records"):
        lines.append("| " + " | ".join(str(record[column]) for column in columns) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
