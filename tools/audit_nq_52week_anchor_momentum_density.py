from __future__ import annotations

import itertools
from pathlib import Path

import pandas as pd
import yaml

CAMPAIGN_ID = "nq_52week_anchor_momentum"
RAW_PARQUET = Path("data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet")
CAMPAIGN_ROOT = Path("campaigns") / CAMPAIGN_ID
OUT_CSV = Path("research_artifacts/nq_52week_anchor_momentum_density_audit_20260701.csv")
OUT_SUMMARY = Path("research_artifacts/nq_52week_anchor_momentum_density_summary_20260701.csv")
OUT_MD = Path("research_artifacts/nq_52week_anchor_momentum_density_audit_20260701.md")

MIN_SIGNALS_PER_YEAR = 50.0
MIN_LATEST_252_SIGNALS = 50


def main() -> None:
    bars = _load_5m_bars()
    sessions = sorted(bars["session_date"].drop_duplicates())
    latest_252_sessions = set(sessions[-252:])
    years = max(len(sessions) / 252.0, 1e-9)
    bars = _add_anchor_state(bars)

    rows = []
    for config_path in sorted(CAMPAIGN_ROOT.glob("variants/*/config.yaml")):
        config = yaml.safe_load(config_path.read_text()) or {}
        variant_id = str(config["variant_id"])
        base_params = dict(config["strategy"]["entry"]["params"])
        entry_grid = {
            key.removeprefix("entry.params."): values
            for key, values in (config["core_grid"]["parameters"] or {}).items()
            if str(key).startswith("entry.params.")
        }
        for combo in _grid_rows(entry_grid):
            params = {**base_params, **combo}
            signals = _count_signals(bars, params)
            latest_252 = sum(1 for day in signals if day in latest_252_sessions)
            signals_per_year = len(signals) / years
            passed = signals_per_year >= MIN_SIGNALS_PER_YEAR and latest_252 >= MIN_LATEST_252_SIGNALS
            rows.append(
                {
                    "campaign_id": CAMPAIGN_ID,
                    "variant_id": variant_id,
                    "entry_combo": ";".join(f"{key}={value}" for key, value in sorted(combo.items())),
                    "full_signals": len(signals),
                    "signals_per_year": signals_per_year,
                    "latest_252_signals": latest_252,
                    "density_pass": passed,
                }
            )

    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby(["campaign_id", "variant_id"], as_index=False)
        .agg(
            entry_rows=("entry_combo", "count"),
            rows_passing_density=("density_pass", "sum"),
            min_full_signals=("full_signals", "min"),
            min_signals_per_year=("signals_per_year", "min"),
            min_latest_252_signals=("latest_252_signals", "min"),
        )
        .assign(variant_density_pass=lambda frame: frame["rows_passing_density"] == frame["entry_rows"])
    )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(OUT_CSV, index=False)
    summary.to_csv(OUT_SUMMARY, index=False)
    _write_markdown(detail, summary)
    print(f"wrote {OUT_MD}")
    print(summary.to_string(index=False))


def _load_5m_bars() -> pd.DataFrame:
    if not RAW_PARQUET.exists():
        raise FileNotFoundError(RAW_PARQUET)
    df = pd.read_parquet(RAW_PARQUET)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["session_date"] = df["timestamp"].dt.date
    df["bar_start"] = df["timestamp"].dt.floor("5min")
    grouped = (
        df.sort_values("timestamp")
        .groupby(["session_date", "bar_start"], sort=True)
        .agg(
            timestamp=("bar_start", "first"),
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .reset_index()
    )
    grouped["is_rth"] = True
    grouped["session_label"] = "RTH"
    return grouped[["timestamp", "session_date", "session_label", "is_rth", "open", "high", "low", "close", "volume"]]


def _add_anchor_state(bars: pd.DataFrame) -> pd.DataFrame:
    out = bars.copy()
    daily = (
        out.groupby("session_date", sort=True)
        .agg(
            session_open=("open", "first"),
            daily_high=("high", "max"),
            daily_low=("low", "min"),
            daily_close=("close", "last"),
        )
        .reset_index()
    )
    daily["anchor_high"] = daily["daily_high"].shift(1).rolling(252, min_periods=252).max()
    daily["anchor_low"] = daily["daily_low"].shift(1).rolling(252, min_periods=252).min()
    daily["prior_close"] = daily["daily_close"].shift(1)
    daily["prior_twenty_low"] = daily["daily_low"].shift(1).rolling(20, min_periods=1).min()
    daily["nearness_to_high"] = daily["prior_close"] / daily["anchor_high"]
    out = out.merge(
        daily[
            [
                "session_date",
                "session_open",
                "anchor_high",
                "anchor_low",
                "prior_close",
                "prior_twenty_low",
                "nearness_to_high",
            ]
        ],
        on="session_date",
        how="left",
    )
    out["bar_close_time"] = (out["timestamp"] + pd.Timedelta(minutes=5)).dt.time
    out["session_return_bps"] = (out["close"] / out["session_open"] - 1.0) * 10000.0
    out["session_low_to_date"] = out.groupby("session_date")["low"].cummin()
    out["session_high_to_date"] = out.groupby("session_date")["high"].cummax()
    return out


def _count_signals(bars: pd.DataFrame, params: dict) -> list:
    mode = str(params["setup_mode"])
    start_time = pd.to_datetime(str(params.get("start_time", "09:45:00"))).time()
    end_time = pd.to_datetime(str(params.get("end_time", "12:30:00"))).time()
    tick_size = float(params.get("tick_size", 0.25))
    buffer = tick_size * float(params.get("breakout_buffer_ticks", 0.0))
    proximity_pct = float(params.get("proximity_pct", 0.02))
    far_from_high_pct = float(params.get("far_from_high_pct", 0.08))
    min_session_return_bps = float(params.get("min_session_return_bps", 0.0))
    pullback_min_bps = float(params.get("pullback_min_bps", 0.0))
    hold_buffer_bps = float(params.get("hold_buffer_bps", 0.0))
    extension_min_bps = float(params.get("extension_min_bps", 0.0))

    window = bars["bar_close_time"].map(lambda value: start_time <= value <= end_time)
    valid_anchor = bars["anchor_high"].notna() & bars["prior_close"].notna()
    near_high = bars["nearness_to_high"] >= 1.0 - proximity_pct
    far_from_high = bars["nearness_to_high"] <= 1.0 - far_from_high_pct

    if mode == "near_high_opening_drive_long":
        mask = valid_anchor & window & near_high & (bars["session_return_bps"] >= min_session_return_bps)
    elif mode == "near_high_breakout_long":
        mask = valid_anchor & window & near_high & (bars["close"] >= bars["anchor_high"] + buffer)
    elif mode == "near_high_pullback_reclaim_long":
        pulled_back = bars["session_low_to_date"] <= bars["prior_close"] * (1.0 - pullback_min_bps / 10000.0)
        mask = (
            valid_anchor
            & window
            & near_high
            & pulled_back
            & (bars["close"] >= bars["prior_close"] + buffer)
            & (bars["session_return_bps"] >= min_session_return_bps)
        )
    elif mode == "near_high_anchor_hold_long":
        held_anchor = bars["session_low_to_date"] >= bars["prior_close"] * (1.0 - hold_buffer_bps / 10000.0)
        mask = valid_anchor & window & near_high & held_anchor & (bars["session_return_bps"] >= min_session_return_bps)
    elif mode == "near_high_extension_hold_long":
        extended = bars["session_high_to_date"] >= bars["prior_close"] * (1.0 + extension_min_bps / 10000.0)
        mask = valid_anchor & window & near_high & extended & (bars["session_return_bps"] >= min_session_return_bps)
    elif mode == "far_from_high_opening_drive_short":
        mask = valid_anchor & window & far_from_high & (bars["session_return_bps"] <= -min_session_return_bps)
    elif mode == "far_from_high_breakdown_short":
        mask = (
            valid_anchor
            & window
            & far_from_high
            & (bars["close"] <= bars["prior_twenty_low"] - buffer)
            & (bars["session_return_bps"] <= -min_session_return_bps)
        )
    else:
        raise ValueError(f"Unsupported setup_mode: {mode}")
    return bars.loc[mask, "session_date"].drop_duplicates().tolist()


def _grid_rows(grid: dict[str, list]) -> list[dict]:
    if not grid:
        return [{}]
    keys = sorted(grid)
    return [dict(zip(keys, values)) for values in itertools.product(*(grid[key] for key in keys))]


def _write_markdown(detail: pd.DataFrame, summary: pd.DataFrame) -> None:
    passed_variants = int(summary["variant_density_pass"].sum())
    passed_rows = int(detail["density_pass"].sum())
    total_rows = int(len(detail))
    verdict = "PASS" if passed_variants == len(summary) and passed_rows == total_rows else "FAIL"
    lines = [
        "# NQ 52-Week Anchor Momentum Density Audit - 2026-07-01",
        "",
        f"Verdict: {verdict}",
        "",
        f"Campaign: `{CAMPAIGN_ID}`",
        f"Entry rows checked: {total_rows}",
        f"Rows passing density: {passed_rows}",
        f"Variants passing all entry rows: {passed_variants}/{len(summary)}",
        "",
        "Criteria:",
        f"- full-history signals per year >= {MIN_SIGNALS_PER_YEAR}",
        f"- latest 252 sessions signals >= {MIN_LATEST_252_SIGNALS}",
        "",
        "This is a pre-PnL opportunity-count screen only. Stops, targets, and PnL were not inspected.",
        "",
        "## Variant Summary",
        "",
        _markdown_table(summary),
        "",
        f"Detail CSV: `{OUT_CSV}`",
        f"Summary CSV: `{OUT_SUMMARY}`",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        values = [str(row[column]) for column in columns]
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


if __name__ == "__main__":
    main()
