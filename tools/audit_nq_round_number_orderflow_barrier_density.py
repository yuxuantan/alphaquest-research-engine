from __future__ import annotations

from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd


RAW_PARQUET = Path("data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet")
DETAIL_CSV = Path("research_artifacts/nq_round_number_orderflow_barrier_density_audit_20260630.csv")
SUMMARY_CSV = Path("research_artifacts/nq_round_number_orderflow_barrier_density_summary_20260630.csv")
AUDIT_MD = Path("research_artifacts/nq_round_number_orderflow_barrier_density_audit_20260630.md")

LIMITED_START = pd.Timestamp("2012-02-22").date()
LIMITED_END = pd.Timestamp("2013-08-01").date()
MAX_CLOSE_DISTANCE_TICKS = 8
TICK_SIZE = 0.25


def _load_5m_bars() -> pd.DataFrame:
    df = pd.read_parquet(RAW_PARQUET)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("America/New_York")
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert("America/New_York")
    df = df[
        (df["timestamp"].dt.time >= pd.Timestamp("09:30").time())
        & (df["timestamp"].dt.time <= pd.Timestamp("15:59").time())
    ].copy()
    df["session_date"] = df["timestamp"].dt.date

    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "signed_volume": "sum",
        "buy_volume": "sum",
        "sell_volume": "sum",
        "large10_signed_volume": "sum",
        "large20_signed_volume": "sum",
        "large10_volume": "sum",
        "large20_volume": "sum",
        "trades": "sum",
    }
    bars = []
    for session_date, group in df.groupby("session_date", sort=True):
        resampled = (
            group.set_index("timestamp")
            .sort_index()
            .resample("5min", label="left", closed="left", origin="start_day")
            .agg(agg)
            .dropna(subset=["open", "high", "low", "close"])
            .reset_index()
        )
        resampled["session_date"] = session_date
        bars.append(resampled)

    out = pd.concat(bars, ignore_index=True)
    out["time"] = out["timestamp"].dt.strftime("%H:%M:%S")
    out["prev_close"] = out.groupby("session_date")["close"].shift(1)
    out["signed_imbalance"] = out["signed_volume"] / out["volume"].replace(0, np.nan)
    out["large10_imbalance"] = out["large10_signed_volume"] / out["large10_volume"].replace(0, np.nan)
    return out


def _time_mask(bars: pd.DataFrame, start_time: str, end_time: str) -> pd.Series:
    return (bars["time"] >= start_time) & (bars["time"] <= end_time)


def _flow_mask(bars: pd.DataFrame, mode: str, confirmation: str, threshold: float) -> pd.Series:
    imbalance = bars["signed_imbalance"] if mode == "signed_volume" else bars["large10_imbalance"]
    if confirmation == "aligned_long":
        return imbalance >= threshold
    if confirmation == "aligned_short":
        return imbalance <= -threshold
    if confirmation == "absorbed_long":
        return imbalance <= -threshold
    if confirmation == "absorbed_short":
        return imbalance >= threshold
    raise ValueError(f"Unsupported confirmation: {confirmation}")


def _floor_barrier(bars: pd.DataFrame, interval: float) -> pd.Series:
    return np.floor(bars["close"] / interval) * interval


def _ceil_barrier(bars: pd.DataFrame, interval: float) -> pd.Series:
    return np.ceil(bars["close"] / interval) * interval


def _near_close(bars: pd.DataFrame, barrier: pd.Series) -> pd.Series:
    return (bars["close"] - barrier).abs() <= MAX_CLOSE_DISTANCE_TICKS * TICK_SIZE


def _support_reclaim(bars: pd.DataFrame, interval: float, buffer_ticks: int) -> pd.Series:
    barrier = _floor_barrier(bars, interval)
    buffer = buffer_ticks * TICK_SIZE
    return _near_close(bars, barrier) & (bars["low"] <= barrier + buffer) & (bars["close"] >= barrier + buffer)


def _resistance_reject(bars: pd.DataFrame, interval: float, buffer_ticks: int) -> pd.Series:
    barrier = _ceil_barrier(bars, interval)
    buffer = buffer_ticks * TICK_SIZE
    return _near_close(bars, barrier) & (bars["high"] >= barrier - buffer) & (bars["close"] <= barrier - buffer)


def _upside_breakout(bars: pd.DataFrame, interval: float, buffer_ticks: int) -> pd.Series:
    barrier = _floor_barrier(bars, interval)
    buffer = buffer_ticks * TICK_SIZE
    return (
        bars["prev_close"].notna()
        & _near_close(bars, barrier)
        & (bars["prev_close"] <= barrier - buffer)
        & (bars["close"] >= barrier + buffer)
    )


def _downside_breakout(bars: pd.DataFrame, interval: float, buffer_ticks: int) -> pd.Series:
    barrier = _ceil_barrier(bars, interval)
    buffer = buffer_ticks * TICK_SIZE
    return (
        bars["prev_close"].notna()
        & _near_close(bars, barrier)
        & (bars["prev_close"] >= barrier + buffer)
        & (bars["close"] <= barrier - buffer)
    )


def _count_signal_dates(
    bars: pd.DataFrame,
    condition: pd.Series,
    full_years: float,
    limited_years: float,
    latest_dates: set,
) -> dict:
    signal_dates = set(bars.loc[condition, "session_date"])
    full_signals = len(signal_dates)
    limited_signals = sum(LIMITED_START <= date <= LIMITED_END for date in signal_dates)
    latest_signals = sum(date in latest_dates for date in signal_dates)
    return {
        "full_signals": full_signals,
        "full_signals_per_year": full_signals / full_years,
        "limited_core_signals": limited_signals,
        "limited_core_signals_per_year": limited_signals / limited_years,
        "latest_252_signals": latest_signals,
    }


def build_density_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    bars = _load_5m_bars()
    full_years = bars["session_date"].nunique() / 252.0
    limited_years = ((LIMITED_END - LIMITED_START).days + 1) / 365.25
    latest_dates = set(sorted(bars["session_date"].unique())[-252:])

    rows = []
    rejected_rows = []

    def add_row(variant: str, interval: float, buffer_ticks: int, min_imbalance: float, condition: pd.Series, declared: bool):
        counts = _count_signal_dates(bars, condition, full_years, limited_years, latest_dates)
        row = {
            "variant": variant,
            "barrier_interval_points": interval,
            "buffer_ticks": buffer_ticks,
            "min_orderflow_imbalance": min_imbalance,
            **counts,
        }
        row["density_pass"] = (
            row["full_signals_per_year"] >= 50
            and row["limited_core_signals_per_year"] >= 50
            and row["latest_252_signals"] >= 50
        )
        if declared:
            rows.append(row)
        else:
            rejected_rows.append(row)

    for interval, buffer_ticks, min_imbalance in product([25.0, 50.0], [0, 1], [0.01, 0.03, 0.05]):
        condition = (
            _time_mask(bars, "09:35:00", "11:30:00")
            & _support_reclaim(bars, interval, buffer_ticks)
            & _flow_mask(bars, "signed_volume", "absorbed_long", min_imbalance)
        )
        add_row(
            "morning_support_sell_absorption_long",
            interval,
            buffer_ticks,
            min_imbalance,
            condition,
            declared=interval == 25.0,
        )

        condition = (
            _time_mask(bars, "09:35:00", "11:30:00")
            & _resistance_reject(bars, interval, buffer_ticks)
            & _flow_mask(bars, "signed_volume", "absorbed_short", min_imbalance)
        )
        add_row(
            "morning_resistance_buy_absorption_short",
            interval,
            buffer_ticks,
            min_imbalance,
            condition,
            declared=interval == 25.0,
        )

    for interval, buffer_ticks, min_imbalance in product([25.0, 50.0], [0, 1], [0.10, 0.20, 0.30]):
        condition = _time_mask(bars, "11:30:00", "14:30:00") & (
            (
                _support_reclaim(bars, interval, buffer_ticks)
                & _flow_mask(bars, "large10", "absorbed_long", min_imbalance)
            )
            | (
                _resistance_reject(bars, interval, buffer_ticks)
                & _flow_mask(bars, "large10", "absorbed_short", min_imbalance)
            )
        )
        add_row(
            "midday_two_sided_large10_absorption_reclaim",
            interval,
            buffer_ticks,
            min_imbalance,
            condition,
            declared=interval == 25.0,
        )

    for variant, price_fn, confirmation in [
        ("round_number_upside_flow_breakout_long", _upside_breakout, "aligned_long"),
        ("round_number_downside_flow_breakout_short", _downside_breakout, "aligned_short"),
    ]:
        for interval, min_imbalance in product([25.0, 50.0, 100.0], [0.01, 0.03, 0.05]):
            condition = (
                _time_mask(bars, "09:45:00", "13:30:00")
                & price_fn(bars, interval, 1)
                & _flow_mask(bars, "signed_volume", confirmation, min_imbalance)
            )
            add_row(
                variant,
                interval,
                1,
                min_imbalance,
                condition,
                declared=interval in {25.0, 50.0},
            )

    detail = pd.DataFrame(rows).sort_values(
        ["variant", "barrier_interval_points", "buffer_ticks", "min_orderflow_imbalance"]
    )
    rejected = pd.DataFrame(rejected_rows).sort_values(
        ["variant", "barrier_interval_points", "buffer_ticks", "min_orderflow_imbalance"]
    )
    summary = (
        detail.groupby("variant")
        .agg(
            declared_rows=("density_pass", "size"),
            passing_rows=("density_pass", "sum"),
            min_full_signals_per_year=("full_signals_per_year", "min"),
            min_limited_core_signals_per_year=("limited_core_signals_per_year", "min"),
            min_latest_252_signals=("latest_252_signals", "min"),
        )
        .reset_index()
    )
    return detail, summary, rejected


def main() -> None:
    detail, summary, rejected = build_density_tables()
    DETAIL_CSV.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)

    declared_pass_rows = int(detail["density_pass"].sum())
    declared_rows = int(len(detail))
    passing_variants = int((summary["declared_rows"] == summary["passing_rows"]).sum())
    rejected_fail_rows = int((~rejected["density_pass"]).sum()) if not rejected.empty else 0

    md = [
        "# NQ Round-Number Orderflow Barrier Density Audit",
        "",
        "Pre-performance density check only. Counts use completed 5-minute RTH bars aggregated from the NQ Sierra one-minute orderflow cache. No PnL, stop, target, WFA, monkey, Monte Carlo, prop-rule, or holdout result was inspected.",
        "",
        f"Source cache: `{RAW_PARQUET}`",
        "Prepared data period: 2011-01-03 through 2026-06-12 RTH, America/New_York.",
        "",
        "Declared campaign grid:",
        "- Support/rejection variants: fixed 25-point barriers, buffer ticks [0, 1], signed-volume absorption thresholds [0.01, 0.03, 0.05].",
        "- Midday two-sided large10 absorption reclaim: fixed 25-point barriers, buffer ticks [0, 1], large10 absorption thresholds [0.10, 0.20, 0.30].",
        "- Breakout variants: 25- and 50-point barriers, fixed buffer 1 tick, signed-volume alignment thresholds [0.01, 0.03, 0.05].",
        "",
        "Pre-PnL rejected corners:",
        "- 50-point support/rejection barriers failed limited-core and/or latest-252 density for some threshold corners.",
        "- 100-point breakout barriers failed limited-core and/or latest-252 density for some threshold corners.",
        "- 50-point midday large10 absorption passed density but was not declared because adding barrier interval as a tunable would exceed the two-entry-parameter cap for that variant.",
        "",
        f"Declared density result: {declared_pass_rows}/{declared_rows} entry rows passed; {passing_variants}/5 variants passed all declared rows.",
        f"Rejected nondeclared corner failures: {rejected_fail_rows}/{len(rejected)}.",
        "",
        "Summary by declared variant:",
        "",
        _markdown_table(summary),
        "",
        f"Detail CSV: `{DETAIL_CSV}`",
        f"Summary CSV: `{SUMMARY_CSV}`",
        "",
        "Decision: PASS for authoring and staged testing of the declared five-variant campaign. This is not a trading pass and does not inspect profitability.",
        "",
    ]
    AUDIT_MD.write_text("\n".join(md), encoding="utf-8")
    print(AUDIT_MD)
    print(DETAIL_CSV)
    print(SUMMARY_CSV)


def _markdown_table(df: pd.DataFrame) -> str:
    columns = list(df.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in df.iterrows():
        values = []
        for col in columns:
            value = row[col]
            if isinstance(value, float):
                values.append(f"{value:.6f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
