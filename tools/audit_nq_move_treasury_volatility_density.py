from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import yaml

CAMPAIGN_ID = "nq_move_treasury_volatility_state"
CAMPAIGN_ROOT = Path("campaigns") / CAMPAIGN_ID
BARS_PATH = Path("data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet")
DETAIL_CSV = Path("research_artifacts/nq_move_treasury_volatility_state_density_audit_20260701.csv")
SUMMARY_CSV = Path("research_artifacts/nq_move_treasury_volatility_state_density_summary_20260701.csv")
SUMMARY_MD = Path("research_artifacts/nq_move_treasury_volatility_state_density_audit_20260701.md")


def main() -> None:
    bars = _load_5m_bars()
    features = pd.read_csv("data/external/nq_move_treasury_vol_features_20110103_20260612.csv")
    bars = bars.merge(features, on="session_date", how="left")
    session_dates = sorted(str(item) for item in bars["session_date"].drop_duplicates())
    latest_252 = set(session_dates[-252:])
    limited_start = pd.Timestamp("2011-01-03")
    limited_end = pd.Timestamp("2012-06-29")
    detail_rows = []
    summary_rows = []

    for config_path in sorted(CAMPAIGN_ROOT.glob("variants/*/config.yaml")):
        config = yaml.safe_load(config_path.read_text())
        variant_id = config["variant_id"]
        entry = config["strategy"]["entry"]
        grid = config["core_grid"]["parameters"]
        rank_values = grid["entry.params.rank_threshold"]
        change_values = grid["entry.params.change_threshold"]
        pass_rows = 0
        variant_rows = []
        for rank_threshold in rank_values:
            for change_threshold in change_values:
                params = dict(entry["params"])
                params["rank_threshold"] = rank_threshold
                params["change_threshold"] = change_threshold
                signals = _count_signals_vectorized(bars, params, latest_252)
                full_per_year = _annualized(signals["full"], session_dates[0], session_dates[-1])
                limited_per_year = _annualized(signals["limited"], limited_start.date().isoformat(), limited_end.date().isoformat())
                latest_count = signals["latest_252"]
                verdict = "PASS" if full_per_year >= 5 and limited_per_year >= 5 and latest_count >= 5 else "FAIL"
                if verdict == "PASS":
                    pass_rows += 1
                row = {
                    "variant": variant_id,
                    "setup_mode": params["setup_mode"],
                    "entry.params.rank_threshold": rank_threshold,
                    "entry.params.change_threshold": change_threshold,
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
    session_open = out.groupby("session_date", sort=False)["open"].transform("first")
    out["rth_return_since_open_ticks"] = (out["close"] - session_open) / 0.25
    out["bar_close_time"] = (out["timestamp"] + pd.Timedelta(minutes=5)).dt.strftime("%H:%M:%S")
    return out.sort_values("timestamp", kind="mergesort").reset_index(drop=True)


def _count_signals_vectorized(bars: pd.DataFrame, params: dict, latest_dates: set[str]) -> dict[str, int]:
    limited_start = pd.Timestamp("2011-01-03").date().isoformat()
    limited_end = pd.Timestamp("2012-06-29").date().isoformat()
    subset = bars[bars["bar_close_time"] == str(params["entry_time"])].copy()
    setup_mode = str(params["setup_mode"])
    rank = float(params["rank_threshold"])
    change = float(params["change_threshold"])
    return_filter = float(params.get("return_filter_ticks", 0.0))

    if setup_mode == "high_move_riskoff_short":
        mask = (subset["move_close_rank_252"] >= rank) & (subset["move_change_5d_rank_252"] >= change)
    elif setup_mode == "low_move_carry_long":
        mask = (subset["move_close_rank_252"] <= 1.0 - rank) & (subset["move_change_5d_rank_252"] <= 1.0 - change)
    elif setup_mode == "move_spike_morning_weakness_short":
        mask = (subset["move_change_1d_rank_252"] >= change) & (
            subset["rth_return_since_open_ticks"] <= -return_filter
        )
    elif setup_mode == "move_crush_morning_strength_long":
        mask = (subset["move_change_1d_rank_252"] <= 1.0 - change) & (
            subset["rth_return_since_open_ticks"] >= return_filter
        )
    elif setup_mode == "move_downshift_riskon_long":
        mask = (subset["move_change_5d_rank_252"] <= 1.0 - change) & (subset["move_close_rank_252"] <= rank)
    else:
        raise ValueError(f"Unsupported setup_mode: {setup_mode}")
    hits = subset[mask.fillna(False)].copy()
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
