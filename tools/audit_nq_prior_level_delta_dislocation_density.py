from __future__ import annotations

import itertools
import json
from pathlib import Path

import pandas as pd

from propstack.data.pipeline import prepare_data


EDGE_ID = "nq_prior_level_delta_dislocation"
AUDIT_DATE = "2026-06-30"
ARTIFACT_STAMP = "20260630"
ARTIFACT_ROOT = Path("research_artifacts")

LIMITED_START = pd.Timestamp("2011-02-22").date()
LIMITED_END = pd.Timestamp("2012-09-07").date()
MIN_FULL_SIGNALS_PER_YEAR = 50.0
MIN_LIMITED_SIGNALS_PER_YEAR = 50.0
MIN_LATEST_252_SIGNALS = 50

ENTRY_MIN_DISTANCE_TICKS = [0, 1, 2]
ENTRY_MIN_HOUR_DELTA = [0, 250, 750]
MAX_DISTANCE_TICKS = 32
SENSITIVITY_MAX_DISTANCE_TICKS = [16, 32, 48, 64, 96, 128, None]

VARIANTS = [
    {
        "variant_id": "pdh_buy_absorption_long",
        "reference_side": "pdh",
        "direction": "long",
        "signal_end": "15:30:00",
    },
    {
        "variant_id": "pdh_buy_exhaustion_short",
        "reference_side": "pdh",
        "direction": "short",
        "signal_end": "15:30:00",
    },
    {
        "variant_id": "pdl_sell_absorption_long",
        "reference_side": "pdl",
        "direction": "long",
        "signal_end": "15:30:00",
    },
    {
        "variant_id": "pdl_sell_pressure_short",
        "reference_side": "pdl",
        "direction": "short",
        "signal_end": "15:30:00",
    },
    {
        "variant_id": "two_sided_auto_level_fade",
        "reference_side": "both",
        "direction": "auto",
        "signal_end": "14:30:00",
    },
]


def main() -> None:
    data, quality = prepare_data(
        _data_config(),
        subset_config=_subset(),
        timeframe="1m",
    )
    data = data.sort_values("timestamp").reset_index(drop=True)
    data["session_date"] = pd.to_datetime(data["session_date"]).dt.date
    data["_bar_close"] = pd.to_datetime(data["timestamp"]) + pd.Timedelta(minutes=1)
    data["_bar_close_seconds"] = _bar_seconds(data["_bar_close"])
    signal_rows = data.loc[data["_bar_close_seconds"].isin(_hour_window_closes())].copy()
    sessions = sorted(data["session_date"].dropna().unique())
    latest_sessions = set(sessions[-252:])

    detail = _detail(signal_rows, sessions, latest_sessions, max_distance_ticks=MAX_DISTANCE_TICKS)
    summary = _summary(detail)
    sensitivity = _sensitivity(signal_rows, sessions, latest_sessions)
    machine_summary = _machine_summary(detail, summary, sensitivity, sessions, quality)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    detail_path = ARTIFACT_ROOT / f"{EDGE_ID}_density_audit_{ARTIFACT_STAMP}.csv"
    summary_path = ARTIFACT_ROOT / f"{EDGE_ID}_density_summary_{ARTIFACT_STAMP}.csv"
    sensitivity_path = ARTIFACT_ROOT / f"{EDGE_ID}_density_sensitivity_{ARTIFACT_STAMP}.csv"
    markdown_path = ARTIFACT_ROOT / f"{EDGE_ID}_density_audit_{ARTIFACT_STAMP}.md"

    detail.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)
    sensitivity.to_csv(sensitivity_path, index=False)
    markdown_path.write_text(
        _markdown(summary, sensitivity, machine_summary, detail_path, summary_path, sensitivity_path),
        encoding="utf-8",
    )
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
        "feature_set": "pdh_pdl_sweep",
        "warmup_days": 30,
        "rth_start": "09:30:00",
        "rth_end": "15:59:00",
        "trade_orderflow_features": {
            "enabled": True,
            "windows": [60],
            "tick_size": 0.25,
            "large_trade_sizes": [10, 20],
            "min_period_fraction": 1.0,
        },
    }


def _subset() -> dict:
    return {
        "start_date": "2011-01-03",
        "end_date": "2026-06-12",
        "session_labels": ["RTH"],
    }


def _detail(
    data: pd.DataFrame,
    sessions: list,
    latest_sessions: set,
    *,
    max_distance_ticks: int | None,
) -> pd.DataFrame:
    rows = []
    for variant in VARIANTS:
        for min_ticks, min_delta in itertools.product(ENTRY_MIN_DISTANCE_TICKS, ENTRY_MIN_HOUR_DELTA):
            signal_dates = _signal_dates(
                data,
                variant,
                min_distance_ticks=min_ticks,
                min_hour_delta=min_delta,
                max_distance_ticks=max_distance_ticks,
            )
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
                    "edge_id": EDGE_ID,
                    "variant_id": variant["variant_id"],
                    "reference_side": variant["reference_side"],
                    "direction": variant["direction"],
                    "signal_start": "10:30:00",
                    "signal_end": variant["signal_end"],
                    "min_close_above_prev_high_ticks": min_ticks,
                    "max_close_above_prev_high_ticks": max_distance_ticks,
                    "min_negative_hour_ticks": 1,
                    "min_hour_delta": min_delta,
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
    return pd.DataFrame(rows)


def _signal_dates(
    data: pd.DataFrame,
    variant: dict,
    *,
    min_distance_ticks: int,
    min_hour_delta: int,
    max_distance_ticks: int | None,
) -> list:
    signal_end_seconds = _time_seconds(variant["signal_end"])
    bars = data.loc[data["_bar_close_seconds"].le(signal_end_seconds)]
    close = pd.to_numeric(bars["close"], errors="coerce")
    hour_return = pd.to_numeric(bars["trade_orderflow_return_points_60"], errors="coerce")
    hour_delta = pd.to_numeric(bars["trade_orderflow_signed_volume_60"], errors="coerce")
    min_distance = min_distance_ticks * 0.25
    max_distance = None if max_distance_ticks is None else max_distance_ticks * 0.25
    min_counter_move = 0.25

    masks = []
    if variant["reference_side"] in {"pdh", "both"}:
        distance = close - pd.to_numeric(bars["prev_rth_high"], errors="coerce")
        mask = distance.ge(min_distance) & hour_return.le(-min_counter_move) & hour_delta.ge(min_hour_delta)
        if max_distance is not None:
            mask &= distance.le(max_distance)
        masks.append(mask)
    if variant["reference_side"] in {"pdl", "both"}:
        distance = pd.to_numeric(bars["prev_rth_low"], errors="coerce") - close
        mask = distance.ge(min_distance) & hour_return.ge(min_counter_move) & hour_delta.le(-min_hour_delta)
        if max_distance is not None:
            mask &= distance.le(max_distance)
        masks.append(mask)

    if not masks:
        return []
    selected = masks[0].copy()
    for mask in masks[1:]:
        selected |= mask
    signals = bars.loc[selected, ["session_date", "timestamp"]]
    if signals.empty:
        return []
    return signals.sort_values("timestamp").drop_duplicates("session_date", keep="first")["session_date"].tolist()


def _sensitivity(data: pd.DataFrame, sessions: list, latest_sessions: set) -> pd.DataFrame:
    rows = []
    for max_distance_ticks in SENSITIVITY_MAX_DISTANCE_TICKS:
        detail = _detail(data, sessions, latest_sessions, max_distance_ticks=max_distance_ticks)
        rows.append(
            {
                "max_close_above_prev_high_ticks": max_distance_ticks,
                "declared_entry_rows": int(len(detail)),
                "density_pass_rows": int(detail["density_gate_pass"].sum()),
                "min_full_signals_per_year": float(detail["full_signals_per_year"].min()),
                "max_full_signals_per_year": float(detail["full_signals_per_year"].max()),
                "min_limited_signals_per_year": float(detail["limited_signals_per_year"].min()),
                "max_limited_signals_per_year": float(detail["limited_signals_per_year"].max()),
                "min_latest_252_signals": int(detail["latest_252_signals"].min()),
                "max_latest_252_signals": int(detail["latest_252_signals"].max()),
                "all_rows_density_pass": bool(detail["density_gate_pass"].all()),
            }
        )
    return pd.DataFrame(rows)


def _summary(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant_id, group in detail.groupby("variant_id", sort=True):
        rows.append(
            {
                "variant_id": variant_id,
                "entry_rows": int(len(group)),
                "pass_rows": int(group["density_gate_pass"].sum()),
                "min_full_signals_per_year": float(group["full_signals_per_year"].min()),
                "median_full_signals_per_year": float(group["full_signals_per_year"].median()),
                "max_full_signals_per_year": float(group["full_signals_per_year"].max()),
                "min_limited_signals_per_year": float(group["limited_signals_per_year"].min()),
                "median_limited_signals_per_year": float(group["limited_signals_per_year"].median()),
                "max_limited_signals_per_year": float(group["limited_signals_per_year"].max()),
                "min_latest_252_signals": int(group["latest_252_signals"].min()),
                "median_latest_252_signals": float(group["latest_252_signals"].median()),
                "max_latest_252_signals": int(group["latest_252_signals"].max()),
                "verdict": "PASS" if bool(group["density_gate_pass"].all()) else "FAIL",
            }
        )
    return pd.DataFrame(rows)


def _machine_summary(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    sensitivity: pd.DataFrame,
    sessions: list,
    quality: dict,
) -> dict:
    best_sensitivity = sensitivity.sort_values(
        ["density_pass_rows", "max_full_signals_per_year", "max_latest_252_signals"],
        ascending=[False, False, False],
    ).iloc[0]
    return {
        "all_rows_density_pass": bool(detail["density_gate_pass"].all()),
        "audit_date": AUDIT_DATE,
        "edge_id": EDGE_ID,
        "declared_entry_rows": int(len(detail)),
        "density_pass_rows": int(detail["density_gate_pass"].sum()),
        "density_fail_rows": int((~detail["density_gate_pass"]).sum()),
        "failed_variants": summary.loc[summary["verdict"] != "PASS", "variant_id"].tolist(),
        "full_start_date": str(sessions[0]),
        "full_end_date": str(sessions[-1]),
        "full_sessions": int(len(sessions)),
        "latest_252_start_date": str(sessions[-252]),
        "latest_252_end_date": str(sessions[-1]),
        "limited_start_date": str(LIMITED_START),
        "limited_end_date": str(LIMITED_END),
        "min_full_signals_per_year": float(detail["full_signals_per_year"].min()),
        "min_limited_signals_per_year": float(detail["limited_signals_per_year"].min()),
        "min_latest_252_signals": int(detail["latest_252_signals"].min()),
        "prepared_rows": int(quality.get("strategy_rows", 0)),
        "sensitivity_best_density_pass_rows": int(best_sensitivity["density_pass_rows"]),
        "sensitivity_best_max_distance_ticks": None
        if pd.isna(best_sensitivity["max_close_above_prev_high_ticks"])
        else int(best_sensitivity["max_close_above_prev_high_ticks"]),
        "sensitivity_best_max_full_signals_per_year": float(best_sensitivity["max_full_signals_per_year"]),
        "sensitivity_best_max_latest_252_signals": int(best_sensitivity["max_latest_252_signals"]),
        "verdict": "FAIL",
        "verdict_reason": "pre-PnL density rejection; exact ES-transfer grid and no-cap sensitivity are below signal-count gates",
    }


def _markdown(
    summary: pd.DataFrame,
    sensitivity: pd.DataFrame,
    machine_summary: dict,
    detail_path: Path,
    summary_path: Path,
    sensitivity_path: Path,
) -> str:
    lines = [
        f"# {EDGE_ID} density audit",
        "",
        f"- Audit date: {AUDIT_DATE}",
        f"- Full window: {machine_summary['full_start_date']} to {machine_summary['full_end_date']} ({machine_summary['full_sessions']} sessions)",
        f"- Limited-core window: {LIMITED_START} to {LIMITED_END}",
        f"- Latest-252 window: {machine_summary['latest_252_start_date']} to {machine_summary['latest_252_end_date']}",
        f"- Exact-transfer max distance: {MAX_DISTANCE_TICKS} ticks",
        f"- Declared entry rows: {machine_summary['declared_entry_rows']}",
        f"- Density passes: {machine_summary['density_pass_rows']}",
        f"- Density failures: {machine_summary['density_fail_rows']}",
        "",
        "Gate: each declared entry row must produce at least 50 signals/year in full history, "
        "at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.",
        "",
        "| variant | rows | pass rows | min full/year | max full/year | min limited/year | max latest-252 | verdict |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary.to_dict("records"):
        lines.append(
            "| {variant_id} | {entry_rows} | {pass_rows} | {min_full_signals_per_year:.2f} | "
            "{max_full_signals_per_year:.2f} | {min_limited_signals_per_year:.2f} | "
            "{max_latest_252_signals} | {verdict} |".format(**row)
        )
    lines.extend(
        [
            "",
            "Sensitivity by fixed max-distance cap:",
            "",
            "| max distance ticks | pass rows | max full/year | max latest-252 | all rows pass |",
            "|---:|---:|---:|---:|---|",
        ]
    )
    for row in sensitivity.to_dict("records"):
        max_distance = "none" if pd.isna(row["max_close_above_prev_high_ticks"]) else int(row["max_close_above_prev_high_ticks"])
        lines.append(
            "| {max_distance} | {density_pass_rows} | {max_full_signals_per_year:.2f} | "
            "{max_latest_252_signals} | {all_rows_density_pass} |".format(
                max_distance=max_distance,
                **row,
            )
        )
    lines.extend(
        [
            "",
            "Machine summary:",
            "",
            "```json",
            json.dumps(machine_summary, indent=2, sort_keys=True),
            "```",
            "",
            f"Detail CSV: `{detail_path}`",
            "",
            f"Summary CSV: `{summary_path}`",
            "",
            f"Sensitivity CSV: `{sensitivity_path}`",
            "",
            "Verdict: FAIL.",
            "",
        ]
    )
    return "\n".join(lines)


def _hour_window_closes() -> set[int]:
    return {
        _time_seconds("10:30:00"),
        _time_seconds("11:30:00"),
        _time_seconds("12:30:00"),
        _time_seconds("13:30:00"),
        _time_seconds("14:30:00"),
        _time_seconds("15:30:00"),
    }


def _bar_seconds(timestamp: pd.Series) -> pd.Series:
    return timestamp.dt.hour * 3600 + timestamp.dt.minute * 60 + timestamp.dt.second


def _time_seconds(value: str) -> int:
    parsed = pd.Timestamp(f"2000-01-01 {value}").time()
    return parsed.hour * 3600 + parsed.minute * 60 + parsed.second


def _per_year(count: int, start_date, end_date) -> float:
    years = max((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days / 365.25, 1 / 365.25)
    return float(count) / years


if __name__ == "__main__":
    main()
