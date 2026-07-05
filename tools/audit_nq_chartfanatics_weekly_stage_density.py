from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import yaml


CAMPAIGN_ID = "nq_chartfanatics_weekly_stage_breakout_bias"
CAMPAIGN_ROOT = Path("campaigns") / CAMPAIGN_ID
BARS_PATH = Path("data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet")
DETAIL_CSV = Path("research_artifacts/nq_chartfanatics_weekly_stage_breakout_bias_density_audit_20260701.csv")
SUMMARY_CSV = Path("research_artifacts/nq_chartfanatics_weekly_stage_breakout_bias_density_summary_20260701.csv")
SUMMARY_MD = Path("research_artifacts/nq_chartfanatics_weekly_stage_breakout_bias_density_audit_20260701.md")


def main() -> None:
    bars = _load_5m_bars()
    bars = _add_daily_weekly_features(bars)
    session_dates = sorted(str(item) for item in bars["session_date"].drop_duplicates())
    latest_252 = set(session_dates[-252:])
    limited_start = "2011-01-03"
    limited_end = "2012-06-29"

    detail_rows: list[dict] = []
    summary_rows: list[dict] = []
    for config_path in sorted(CAMPAIGN_ROOT.glob("variants/*/config.yaml")):
        config = yaml.safe_load(config_path.read_text())
        variant_id = config["variant_id"]
        entry = config["strategy"]["entry"]
        grid = config["core_grid"]["parameters"]
        threshold_values = grid["entry.params.stage_strength_threshold"]
        breakout_values = grid["entry.params.min_breakout_ticks"]
        pass_rows = 0
        variant_rows: list[dict] = []
        for stage_threshold in threshold_values:
            for min_breakout_ticks in breakout_values:
                params = dict(entry["params"])
                params["stage_strength_threshold"] = stage_threshold
                params["min_breakout_ticks"] = min_breakout_ticks
                signals = _count_signals(bars, params, latest_252, limited_start, limited_end)
                full_per_year = _annualized(signals["full"], session_dates[0], session_dates[-1])
                limited_per_year = _annualized(signals["limited"], limited_start, limited_end)
                latest_count = signals["latest_252"]
                verdict = "PASS" if full_per_year >= 5 and limited_per_year >= 5 and latest_count >= 5 else "FAIL"
                if verdict == "PASS":
                    pass_rows += 1
                row = {
                    "variant": variant_id,
                    "setup_mode": params["setup_mode"],
                    "entry.params.stage_strength_threshold": stage_threshold,
                    "entry.params.min_breakout_ticks": min_breakout_ticks,
                    "full_signals": signals["full"],
                    "full_signals_per_year": full_per_year,
                    "limited_signals": signals["limited"],
                    "limited_signals_per_year": limited_per_year,
                    "latest_252_signals": latest_count,
                    "verdict": verdict,
                }
                detail_rows.append(row)
                variant_rows.append(row)
        summary_rows.append(
            {
                "variant": variant_id,
                "rows": len(variant_rows),
                "pass_rows": pass_rows,
                "min_full_per_year": min(row["full_signals_per_year"] for row in variant_rows),
                "min_limited_per_year": min(row["limited_signals_per_year"] for row in variant_rows),
                "min_latest_252": min(row["latest_252_signals"] for row in variant_rows),
                "max_full_per_year": max(row["full_signals_per_year"] for row in variant_rows),
                "verdict": "PASS" if pass_rows == len(variant_rows) else "FAIL",
            }
        )

    DETAIL_CSV.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(DETAIL_CSV, detail_rows)
    _write_csv(SUMMARY_CSV, summary_rows)
    campaign_pass = all(row["verdict"] == "PASS" for row in summary_rows)
    lines = [
        f"# {CAMPAIGN_ID} Density Audit",
        "",
        f"Decision: {'PASS' if campaign_pass else 'FAIL'}",
        "",
        "Gate: every declared entry row must have at least 5 full-history signals/year, 5 early-window signals/year, and 5 signals in the latest 252 sessions.",
        "",
        "| variant | pass_rows | rows | min_full_per_year | min_limited_per_year | min_latest_252 | verdict |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['variant']} | {row['pass_rows']} | {row['rows']} | "
            f"{row['min_full_per_year']:.2f} | {row['min_limited_per_year']:.2f} | "
            f"{row['min_latest_252']} | {row['verdict']} |"
        )
    lines += ["", f"Detail CSV: `{DETAIL_CSV}`", f"Summary CSV: `{SUMMARY_CSV}`"]
    SUMMARY_MD.write_text("\n".join(lines) + "\n")
    print(f"wrote {SUMMARY_MD}")
    print(f"density rows passing {sum(row['verdict'] == 'PASS' for row in detail_rows)}/{len(detail_rows)}")
    print(f"variants passing {sum(row['verdict'] == 'PASS' for row in summary_rows)}/{len(summary_rows)}")
    print(f"decision {'PASS' if campaign_pass else 'FAIL'}")


def _load_5m_bars() -> pd.DataFrame:
    raw = pd.read_parquet(BARS_PATH)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"])
    if raw["timestamp"].dt.tz is None:
        raw["timestamp"] = raw["timestamp"].dt.tz_localize("America/New_York")
    else:
        raw["timestamp"] = raw["timestamp"].dt.tz_convert("America/New_York")
    raw = raw[
        (raw["timestamp"].dt.time >= pd.Timestamp("09:30").time())
        & (raw["timestamp"].dt.time <= pd.Timestamp("15:59").time())
    ].copy()
    raw["session_date"] = raw["timestamp"].dt.date.astype(str)
    raw["bucket"] = raw["timestamp"].dt.floor("5min")
    grouped = raw.groupby(["session_date", "bucket"], sort=True)
    out = grouped.agg(
        timestamp=("bucket", "first"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).reset_index()
    out = out.drop(columns=["bucket"])
    out["is_rth"] = True
    out["bar_close_time"] = (out["timestamp"] + pd.Timedelta(minutes=5)).dt.strftime("%H:%M:%S")
    return out.sort_values("timestamp", kind="mergesort").reset_index(drop=True)


def _add_daily_weekly_features(bars: pd.DataFrame) -> pd.DataFrame:
    daily = bars.groupby("session_date", sort=True).agg(
        daily_open=("open", "first"),
        daily_high=("high", "max"),
        daily_low=("low", "min"),
        daily_close=("close", "last"),
    ).reset_index()
    daily["session_ts"] = pd.to_datetime(daily["session_date"])
    daily["weekly_period"] = daily["session_ts"].dt.to_period("W-FRI")

    weekly = daily.groupby("weekly_period", sort=True).agg(
        weekly_open=("daily_open", "first"),
        weekly_high=("daily_high", "max"),
        weekly_low=("daily_low", "min"),
        weekly_close=("daily_close", "last"),
    ).reset_index()
    close = weekly["weekly_close"]
    weekly["ma10"] = close.rolling(10).mean()
    weekly["ma20"] = close.rolling(20).mean()
    weekly["ma30"] = close.rolling(30).mean()
    weekly["ma40"] = close.rolling(40).mean()
    weekly["prev_ma10"] = weekly["ma10"].shift(1)
    weekly["prev_ma20"] = weekly["ma20"].shift(1)
    weekly["prior4_high"] = weekly["weekly_high"].shift(1).rolling(4).max()
    weekly["prior4_low"] = weekly["weekly_low"].shift(1).rolling(4).min()
    weekly["stage2_score"] = (
        (weekly["weekly_close"] > weekly["ma10"]).astype(int)
        + (weekly["weekly_close"] > weekly["ma20"]).astype(int)
        + (weekly["weekly_close"] > weekly["ma30"]).astype(int)
        + (weekly["weekly_close"] > weekly["ma40"]).astype(int)
        + ((weekly["ma10"] > weekly["ma20"]) & (weekly["ma20"] > weekly["ma30"])).astype(int)
        + (weekly["ma10"] > weekly["prev_ma10"]).astype(int)
        + (weekly["ma20"] > weekly["prev_ma20"]).astype(int)
        + (weekly["weekly_high"] >= weekly["prior4_high"]).astype(int)
    )
    weekly["stage4_score"] = (
        (weekly["weekly_close"] < weekly["ma10"]).astype(int)
        + (weekly["weekly_close"] < weekly["ma20"]).astype(int)
        + (weekly["weekly_close"] < weekly["ma30"]).astype(int)
        + (weekly["weekly_close"] < weekly["ma40"]).astype(int)
        + ((weekly["ma10"] < weekly["ma20"]) & (weekly["ma20"] < weekly["ma30"])).astype(int)
        + (weekly["ma10"] < weekly["prev_ma10"]).astype(int)
        + (weekly["ma20"] < weekly["prev_ma20"]).astype(int)
        + (weekly["weekly_low"] <= weekly["prior4_low"]).astype(int)
    )
    stage_cols = ["weekly_period", "ma10", "ma20", "stage2_score", "stage4_score"]
    prior_stage = weekly[stage_cols].copy()
    prior_stage["weekly_period"] = prior_stage["weekly_period"] + 1

    daily["prior_high"] = daily["daily_high"].shift(1)
    daily["prior_low"] = daily["daily_low"].shift(1)
    daily["prior_close"] = daily["daily_close"].shift(1)
    daily["prior5_high"] = daily["daily_high"].shift(1).rolling(5).max()
    daily["prior5_low"] = daily["daily_low"].shift(1).rolling(5).min()
    daily = daily.merge(prior_stage, on="weekly_period", how="left")
    daily["weekly_support"] = daily[["ma10", "ma20"]].max(axis=1)

    bars = bars.merge(
        daily[
            [
                "session_date",
                "prior_high",
                "prior_low",
                "prior_close",
                "prior5_high",
                "prior5_low",
                "weekly_support",
                "stage2_score",
                "stage4_score",
            ]
        ],
        on="session_date",
        how="left",
    )
    opening = bars[bars["bar_close_time"] <= "09:45:00"].groupby("session_date", sort=True).agg(
        opening_range_high=("high", "max"),
        opening_range_low=("low", "min"),
    ).reset_index()
    bars = bars.merge(opening, on="session_date", how="left")
    return bars


def _count_signals(
    bars: pd.DataFrame,
    params: dict,
    latest_dates: set[str],
    limited_start: str,
    limited_end: str,
) -> dict[str, int]:
    subset = bars[
        (bars["bar_close_time"] >= str(params["start_time"]))
        & (bars["bar_close_time"] <= str(params["end_time"]))
    ].copy()
    threshold = int(params["stage_strength_threshold"])
    buffer = float(params["min_breakout_ticks"]) * float(params.get("tick_size", 0.25))
    mask = (subset["stage2_score"] >= threshold) & (subset["stage4_score"] < threshold)
    mode = str(params["setup_mode"])
    if mode == "stage2_opening_range_breakout":
        mask &= subset["close"] >= subset["opening_range_high"] + buffer
    elif mode == "stage2_prior_high_reclaim":
        mask &= (subset["high"] >= subset["prior_high"] + buffer) & (subset["close"] >= subset["prior_high"])
    elif mode == "stage2_prior_close_reclaim":
        mask &= (subset["low"] <= subset["prior_close"]) & (subset["close"] >= subset["prior_close"] + buffer)
    elif mode == "stage2_weekly_support_reclaim":
        proximity = float(params.get("support_proximity_pct", 0.015))
        mask &= (subset[["prior_low", "low"]].min(axis=1) <= subset["weekly_support"] * (1.0 + proximity)) & (
            subset["close"] >= subset["prior_close"] + buffer
        )
    elif mode == "stage2_compression_breakout":
        midpoint = (subset["prior5_high"] + subset["prior5_low"]) / 2.0
        compression = (subset["prior5_high"] - subset["prior5_low"]) / midpoint
        mask &= (compression <= float(params.get("consolidation_max_range_pct", 0.03))) & (
            subset["close"] >= subset["prior5_high"] + buffer
        )
    else:
        raise ValueError(f"Unsupported setup_mode: {mode}")
    hits = subset[mask.fillna(False)].drop_duplicates("session_date")
    return {
        "full": int(len(hits)),
        "limited": int(((hits["session_date"] >= limited_start) & (hits["session_date"] <= limited_end)).sum()),
        "latest_252": int(hits["session_date"].isin(latest_dates).sum()),
    }


def _annualized(count: int, start: str, end: str) -> float:
    days = max((pd.Timestamp(end) - pd.Timestamp(start)).days + 1, 1)
    return count / (days / 365.25)


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
