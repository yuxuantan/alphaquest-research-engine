from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


CAMPAIGN_ID = "nq_treasury_rate_orderflow_confirmation"
ARTIFACT_STAMP = "20260630"
RAW_PARQUET = Path("data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet")
VARIANT_ROOT = Path("campaigns") / CAMPAIGN_ID / "variants"
ARTIFACT_ROOT = Path("research_artifacts")
DETAIL_CSV = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.csv"
SUMMARY_CSV = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_summary_{ARTIFACT_STAMP}.csv"
AUDIT_MD = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.md"

LIMITED_START = pd.Timestamp("2011-02-22").date()
LIMITED_END = pd.Timestamp("2012-09-07").date()
MIN_FULL_SIGNALS_PER_YEAR = 50.0
MIN_LIMITED_SIGNALS_PER_YEAR = 50.0
MIN_LATEST_252_SIGNALS = 50

RANK_COLUMNS = {
    "dgs10_1d": "dgs10_change_1d_rank_252",
    "dgs2_1d": "dgs2_change_1d_rank_252",
    "curve_1d": "curve_change_1d_rank_252",
    "dgs10_5d": "dgs10_change_5d_rank_252",
    "curve_5d": "curve_change_5d_rank_252",
}
FLOW_COLUMNS = {
    "signed_volume": ("cum_signed_volume", "cum_volume"),
    "large10": ("cum_large10_signed_volume", "cum_large10_volume"),
    "large20": ("cum_large20_signed_volume", "cum_large20_volume"),
}
_FEATURE_CACHE: dict[str, pd.DataFrame] = {}


def main() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    bars = _load_5m_bars()
    detail = _build_detail(bars)
    summary = _build_summary(detail)

    detail.to_csv(DETAIL_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)
    AUDIT_MD.write_text(_markdown(detail, summary), encoding="utf-8")

    passing = int(detail["density_gate_pass"].sum())
    print(f"{CAMPAIGN_ID}: density rows passing {passing}/{len(detail)}")
    print(f"detail={DETAIL_CSV}")
    print(f"summary={SUMMARY_CSV}")
    print(f"audit={AUDIT_MD}")


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
        "large10_signed_volume": "sum",
        "large10_volume": "sum",
        "large20_signed_volume": "sum",
        "large20_volume": "sum",
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
        resampled["is_rth"] = True
        bars.append(resampled)
    out = pd.concat(bars, ignore_index=True).sort_values("timestamp")
    for column in (
        "volume",
        "signed_volume",
        "large10_signed_volume",
        "large10_volume",
        "large20_signed_volume",
        "large20_volume",
    ):
        out[f"cum_{column}"] = out.groupby("session_date")[column].cumsum()
    out["session_open"] = out.groupby("session_date")["open"].transform("first")
    out["move_ticks"] = (out["close"] - out["session_open"]) / 0.25
    out["signal_time"] = (out["timestamp"] + pd.Timedelta(minutes=5)).dt.strftime("%H:%M:%S")
    return out


def _build_detail(bars: pd.DataFrame) -> pd.DataFrame:
    session_dates = sorted(bars["session_date"].unique())
    full_years = len(session_dates) / 252.0
    limited_dates = {d for d in session_dates if LIMITED_START <= d <= LIMITED_END}
    limited_years = len(limited_dates) / 252.0
    latest_dates = set(session_dates[-252:])

    rows = []
    for cfg_path in sorted(VARIANT_ROOT.glob("*/config.yaml")):
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        variant_id = cfg["variant_id"]
        base_params = cfg["strategy"]["entry"]["params"]
        grid = cfg["core_grid"]["parameters"]
        for rate_rank_threshold in grid["entry.params.rate_rank_threshold"]:
            for min_orderflow_imbalance in grid["entry.params.min_orderflow_imbalance"]:
                params = deepcopy(base_params)
                params["rate_rank_threshold"] = float(rate_rank_threshold)
                params["min_orderflow_imbalance"] = float(min_orderflow_imbalance)
                signal_dates = _signal_dates(bars, params)
                full_signals = len(signal_dates)
                limited_signals = sum(d in limited_dates for d in signal_dates)
                latest_signals = sum(d in latest_dates for d in signal_dates)
                full_rate = full_signals / full_years if full_years else 0.0
                limited_rate = limited_signals / limited_years if limited_years else 0.0
                density_gate_pass = (
                    full_rate >= MIN_FULL_SIGNALS_PER_YEAR
                    and limited_rate >= MIN_LIMITED_SIGNALS_PER_YEAR
                    and latest_signals >= MIN_LATEST_252_SIGNALS
                )
                rows.append(
                    {
                        "campaign_id": CAMPAIGN_ID,
                        "variant_id": variant_id,
                        "rank_mode": params["rank_mode"],
                        "flow_mode": params["flow_mode"],
                        "rate_rank_threshold": float(rate_rank_threshold),
                        "min_orderflow_imbalance": float(min_orderflow_imbalance),
                        "full_signals": full_signals,
                        "full_signals_per_year": full_rate,
                        "limited_core_start": LIMITED_START.isoformat(),
                        "limited_core_end": LIMITED_END.isoformat(),
                        "limited_core_signals": limited_signals,
                        "limited_core_signals_per_year": limited_rate,
                        "latest_252_signals": latest_signals,
                        "density_gate_pass": bool(density_gate_pass),
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["variant_id", "rate_rank_threshold", "min_orderflow_imbalance"]
    )


def _signal_dates(bars: pd.DataFrame, params: dict) -> set:
    feature_csv = str(params["feature_csv"])
    rank_mode = str(params["rank_mode"])
    flow_mode = str(params["flow_mode"])
    rank_column = RANK_COLUMNS[rank_mode]
    signed_column, volume_column = FLOW_COLUMNS[flow_mode]
    features = _load_features(feature_csv)
    work = bars.join(features[[rank_column]], on="session_date", how="left")

    rank = work[rank_column].astype(float)
    threshold = float(params["rate_rank_threshold"])
    low_tail = 1.0 - threshold
    min_move_ticks = float(params.get("min_es_move_ticks", 0.0))
    min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
    min_flow_volume = float(params.get("min_flow_volume", 0.0))
    signal_times = {str(value) for value in params["signal_times"]}

    signed_volume = work[signed_column].astype(float)
    flow_volume = work[volume_column].replace(0, np.nan).astype(float)
    imbalance = signed_volume / flow_volume

    short_condition = (
        rank.ge(threshold)
        & work["move_ticks"].le(-min_move_ticks)
        & flow_volume.ge(min_flow_volume)
        & imbalance.le(-min_orderflow_imbalance)
    )
    long_condition = (
        rank.le(low_tail)
        & work["move_ticks"].ge(min_move_ticks)
        & flow_volume.ge(min_flow_volume)
        & imbalance.ge(min_orderflow_imbalance)
    )
    condition = work["signal_time"].isin(signal_times) & (short_condition | long_condition)
    signaled = work.loc[condition, ["session_date", "timestamp"]].sort_values(["session_date", "timestamp"])
    return set(signaled.drop_duplicates("session_date")["session_date"])


def _load_features(path: str) -> pd.DataFrame:
    if path not in _FEATURE_CACHE:
        features = pd.read_csv(path)
        features["session_date"] = pd.to_datetime(features["session_date"]).dt.date
        _FEATURE_CACHE[path] = features.set_index("session_date")
    return _FEATURE_CACHE[path]


def _build_summary(detail: pd.DataFrame) -> pd.DataFrame:
    summary = (
        detail.groupby("variant_id")
        .agg(
            declared_entry_rows=("density_gate_pass", "size"),
            passing_entry_rows=("density_gate_pass", "sum"),
            min_full_signals_per_year=("full_signals_per_year", "min"),
            min_limited_core_signals_per_year=("limited_core_signals_per_year", "min"),
            min_latest_252_signals=("latest_252_signals", "min"),
        )
        .reset_index()
    )
    summary["variant_density_gate_pass"] = summary["passing_entry_rows"].eq(summary["declared_entry_rows"])
    summary["verdict"] = summary["variant_density_gate_pass"].map({True: "PASS", False: "FAIL"})
    return summary.sort_values(["variant_density_gate_pass", "variant_id"], ascending=[False, True])


def _markdown(detail: pd.DataFrame, summary: pd.DataFrame) -> str:
    all_rows_pass = bool(detail["density_gate_pass"].all())
    all_variants_pass = bool(summary["variant_density_gate_pass"].all())
    verdict = "PASS" if all_rows_pass and all_variants_pass else "FAIL"
    lines = [
        f"# {CAMPAIGN_ID} density audit",
        "",
        f"Verdict: {verdict}.",
        "",
        "This is a pre-PnL density audit. It counts only signal availability from completed 5-minute NQ RTH bars, lagged Treasury features whose observation date is strictly before the NQ session date, and the declared entry-parameter grid. It does not inspect stops, targets, trade outcomes, equity curves, WFA, Monte Carlo, or prop-rule outcomes.",
        "",
        f"- Detail CSV: `{DETAIL_CSV}`",
        f"- Summary CSV: `{SUMMARY_CSV}`",
        f"- Full-history threshold: >= {MIN_FULL_SIGNALS_PER_YEAR:.0f} signals/year",
        f"- Limited-core window: {LIMITED_START.isoformat()} through {LIMITED_END.isoformat()}, threshold >= {MIN_LIMITED_SIGNALS_PER_YEAR:.0f} signals/year",
        f"- Latest-252 threshold: >= {MIN_LATEST_252_SIGNALS} signals",
        f"- Density rows passing: {int(detail['density_gate_pass'].sum())}/{len(detail)}",
        f"- Variants passing all declared rows: {int(summary['variant_density_gate_pass'].sum())}/{len(summary)}",
        "",
        "| variant | rows | pass rows | min full/year | min limited/year | min latest 252 | verdict |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary.to_dict("records"):
        lines.append(
            "| {variant_id} | {declared_entry_rows} | {passing_entry_rows} | "
            "{min_full_signals_per_year:.2f} | {min_limited_core_signals_per_year:.2f} | "
            "{min_latest_252_signals} | {verdict} |".format(**row)
        )
    lines.append("")
    if verdict == "FAIL":
        lines.append("Conclusion: reject before staged PnL unless the user explicitly authorizes a different edge or a rescue. The declared family does not clear the pre-performance opportunity-count gate.")
    else:
        lines.append("Conclusion: density is sufficient to proceed to preflight and staged validation. This is not evidence of profitability.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
