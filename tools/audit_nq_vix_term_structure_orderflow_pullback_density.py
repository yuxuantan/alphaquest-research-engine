from __future__ import annotations

import itertools
from pathlib import Path

import pandas as pd
import yaml

from propstack.research.campaign_stages import DEFAULT_SHORTLIST_DATA_WINDOW, _subset_from_window
from propstack.strategy_modules.entry.vix_term_structure_orderflow_pullback import (
    TERM_STATE_RULES,
    VixTermStructureOrderflowPullbackEntry,
)


CAMPAIGN_ID = "nq_vix_term_structure_orderflow_pullback"
ARTIFACT_STAMP = "20260701"
VARIANT_ROOT = Path("campaigns") / CAMPAIGN_ID / "variants"
ARTIFACT_ROOT = Path("research_artifacts")
DETAIL_CSV = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.csv"
SUMMARY_CSV = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_summary_{ARTIFACT_STAMP}.csv"
AUDIT_MD = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.md"
BAR_CACHE = Path("data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet")
MIN_SIGNALS_PER_YEAR = 50.0
NEEDED_COLUMNS = [
    "timestamp",
    "session_date",
    "session_label",
    "is_rth",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "signed_volume",
    "large10_signed_volume",
    "large10_volume",
    "large20_signed_volume",
    "large20_volume",
    "vwap",
]


def main() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    bars = _load_bars()
    config_paths = sorted(VARIANT_ROOT.glob("*/config.yaml"))
    if not config_paths:
        raise FileNotFoundError(f"No variant configs found under {VARIANT_ROOT}")
    first_cfg = yaml.safe_load(config_paths[0].read_text(encoding="utf-8"))
    limited_subset = _subset_from_window(first_cfg["core"]["data_subset"], DEFAULT_SHORTLIST_DATA_WINDOW)
    detail = _build_detail(bars, limited_subset)
    summary = _build_summary(detail)
    detail.to_csv(DETAIL_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)
    AUDIT_MD.write_text(_markdown(bars, detail, summary, limited_subset), encoding="utf-8")
    print(f"{CAMPAIGN_ID}: density rows passing {int(detail['density_gate_pass'].sum())}/{len(detail)}")
    print(f"variants passing {int(summary['density_gate_pass'].sum())}/{len(summary)}")
    print(f"detail={DETAIL_CSV}")
    print(f"summary={SUMMARY_CSV}")
    print(f"audit={AUDIT_MD}")


def _load_bars() -> pd.DataFrame:
    df = pd.read_parquet(BAR_CACHE)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["session_date"] = df["timestamp"].dt.date
    if "session_label" not in df.columns:
        df["session_label"] = "RTH"
    if "is_rth" not in df.columns:
        df["is_rth"] = True
    if "vwap" not in df.columns:
        typical = (df["high"] + df["low"] + df["close"]) / 3.0
        pv = typical * df["volume"]
        df["_pv"] = pv
        df["_cum_pv"] = df.groupby(["session_date", "session_label"])["_pv"].cumsum()
        df["_cum_vol"] = df.groupby(["session_date", "session_label"])["volume"].cumsum()
        df["vwap"] = df["_cum_pv"] / df["_cum_vol"].replace(0, pd.NA)
        df = df.drop(columns=["_pv", "_cum_pv", "_cum_vol"])
    df = df[df["is_rth"].astype(bool)].copy()
    missing = [col for col in NEEDED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"NQ bar cache missing density columns: {missing}")
    return df[NEEDED_COLUMNS].sort_values(["timestamp"], kind="mergesort").reset_index(drop=True)


def _build_detail(bars: pd.DataFrame, limited_subset: dict) -> pd.DataFrame:
    full_dates = sorted(set(bars["session_date"]))
    limited_dates = _subset_dates(full_dates, limited_subset)
    full_years = len(full_dates) / 252.0
    limited_years = len(limited_dates) / 252.0 if limited_dates else 0.0
    rows = []
    for cfg_path in sorted(VARIANT_ROOT.glob("*/config.yaml")):
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        variant_id = cfg["variant_id"]
        params = dict(cfg["strategy"]["entry"]["params"])
        feature_rows = _feature_rows(Path(params["feature_csv"]))
        entry_grid = cfg["core_grid"]["parameters"]
        for term_rank_threshold, min_orderflow_imbalance in itertools.product(
            entry_grid["entry.params.term_rank_threshold"],
            entry_grid["entry.params.min_orderflow_imbalance"],
        ):
            test_params = dict(params)
            test_params["term_rank_threshold"] = float(term_rank_threshold)
            test_params["min_orderflow_imbalance"] = float(min_orderflow_imbalance)
            eligible_dates = _eligible_term_dates(feature_rows, test_params)
            signal_times = _signal_times(bars, test_params, eligible_dates)
            signal_dates = {ts.date() for ts in signal_times}
            limited_signal_times = [ts for ts in signal_times if ts.date() in limited_dates]
            full_signals = len(signal_times)
            limited_signals = len(limited_signal_times)
            full_rate = full_signals / full_years if full_years else 0.0
            limited_rate = limited_signals / limited_years if limited_years else 0.0
            density_gate_pass = full_rate >= MIN_SIGNALS_PER_YEAR and limited_rate >= MIN_SIGNALS_PER_YEAR
            rows.append(
                {
                    "campaign_id": CAMPAIGN_ID,
                    "variant_id": variant_id,
                    "term_setup_mode": test_params["term_setup_mode"],
                    "flow_mode": test_params["flow_mode"],
                    "start_time": str(test_params["start_time"]),
                    "end_time": str(test_params["end_time"]),
                    "term_rank_threshold": float(term_rank_threshold),
                    "min_orderflow_imbalance": float(min_orderflow_imbalance),
                    "eligible_term_sessions": len(eligible_dates),
                    "full_signals": full_signals,
                    "full_trades_per_year": full_rate,
                    "limited_core_start": limited_subset.get("start_date"),
                    "limited_core_end": limited_subset.get("end_date"),
                    "limited_core_signals": limited_signals,
                    "limited_core_trades_per_year": limited_rate,
                    "unique_signal_dates": len(signal_dates),
                    "full_first_signal": _iso_or_blank(signal_times[0] if signal_times else None),
                    "full_last_signal": _iso_or_blank(signal_times[-1] if signal_times else None),
                    "limited_first_signal": _iso_or_blank(limited_signal_times[0] if limited_signal_times else None),
                    "limited_last_signal": _iso_or_blank(limited_signal_times[-1] if limited_signal_times else None),
                    "density_gate_pass": bool(density_gate_pass),
                }
            )
    return pd.DataFrame(rows).sort_values(["variant_id", "term_rank_threshold", "min_orderflow_imbalance"])


def _feature_rows(path: Path) -> dict:
    df = pd.read_csv(path)
    df["session_date"] = pd.to_datetime(df["session_date"]).dt.date
    return df.set_index("session_date").to_dict("index")


def _eligible_term_dates(feature_rows: dict, params: dict) -> set:
    column, op, _direction = TERM_STATE_RULES[params["term_setup_mode"]]
    threshold = float(params["term_rank_threshold"])
    out = set()
    for session_date, row in feature_rows.items():
        value = row.get(column)
        if pd.isna(value):
            continue
        rank = float(value)
        if op == "<=" and rank <= threshold:
            out.add(session_date)
        elif op == ">=" and rank >= threshold:
            out.add(session_date)
    return out


def _signal_times(bars: pd.DataFrame, params: dict, eligible_dates: set) -> list[pd.Timestamp]:
    if not eligible_dates:
        return []
    date_mask = bars["session_date"].isin(eligible_dates)
    if not bool(date_mask.any()):
        return []
    subset = bars.loc[date_mask].copy()
    entry = VixTermStructureOrderflowPullbackEntry(params)
    signal_dates = set()
    signal_times = []
    columns = list(subset.columns)
    for name, values in zip(subset.index, subset.itertuples(index=False, name=None), strict=True):
        row = _AuditRow(columns, values, int(name))
        session_date = row["session_date"]
        signal = entry.on_bar_close(row, trades_today=1 if session_date in signal_dates else 0)
        if signal is not None:
            signal_dates.add(session_date)
            signal_times.append(pd.Timestamp(row["timestamp"]))
    return signal_times


def _subset_dates(session_dates: list, subset: dict) -> set:
    start = pd.Timestamp(subset["start_date"]).date()
    end = pd.Timestamp(subset["end_date"]).date()
    return {d for d in session_dates if start <= d <= end}


def _build_summary(detail: pd.DataFrame) -> pd.DataFrame:
    passing = detail[detail["density_gate_pass"]].copy()
    best_rows = (
        passing.sort_values(["variant_id", "full_trades_per_year", "limited_core_trades_per_year"], ascending=[True, False, False])
        .groupby("variant_id")
        .head(1)
    )
    summary = (
        detail.groupby("variant_id")
        .agg(
            declared_entry_rows=("density_gate_pass", "size"),
            passing_entry_rows=("density_gate_pass", "sum"),
            best_full_signals=("full_signals", "max"),
            best_full_trades_per_year=("full_trades_per_year", "max"),
            best_limited_core_signals=("limited_core_signals", "max"),
            best_limited_core_trades_per_year=("limited_core_trades_per_year", "max"),
        )
        .reset_index()
    )
    summary["density_gate_pass"] = summary["passing_entry_rows"].gt(0)
    summary["verdict"] = summary["density_gate_pass"].map({True: "PASS", False: "FAIL"})
    if not best_rows.empty:
        best_rows = best_rows[
            [
                "variant_id",
                "term_rank_threshold",
                "min_orderflow_imbalance",
                "full_signals",
                "full_trades_per_year",
                "limited_core_signals",
                "limited_core_trades_per_year",
            ]
        ].rename(
            columns={
                "term_rank_threshold": "passing_term_rank_threshold",
                "min_orderflow_imbalance": "passing_min_orderflow_imbalance",
                "full_signals": "passing_full_signals",
                "full_trades_per_year": "passing_full_trades_per_year",
                "limited_core_signals": "passing_limited_core_signals",
                "limited_core_trades_per_year": "passing_limited_core_trades_per_year",
            }
        )
        summary = summary.merge(best_rows, on="variant_id", how="left")
    return summary.sort_values(["density_gate_pass", "variant_id"], ascending=[False, True])


def _markdown(bars: pd.DataFrame, detail: pd.DataFrame, summary: pd.DataFrame, limited_subset: dict) -> str:
    verdict = "PASS" if bool(summary["density_gate_pass"].all()) else "FAIL"
    full_subset = {
        "start_date": min(bars["session_date"]).isoformat(),
        "end_date": max(bars["session_date"]).isoformat(),
        "session_labels": ["RTH"],
    }
    lines = [
        f"# {CAMPAIGN_ID} pre-PnL density audit",
        "",
        f"Verdict: {verdict}.",
        "",
        "This audit uses only declared entry predicates: lagged VIX term-state rank, completed NQ VWAP context, completed aggregate orderflow, configured signal window, and max one signal per session. It does not inspect PnL, stops, targets, fills, WFA, Monte Carlo, prop-rule outcomes, or future returns.",
        "",
        f"- Detail CSV: `{DETAIL_CSV}`",
        f"- Summary CSV: `{SUMMARY_CSV}`",
        f"- NQ bar cache: `{BAR_CACHE}`",
        f"- Full configured subset: `{full_subset}`",
        f"- Resolved limited-core subset: `{limited_subset}`",
        f"- Full rows: `{len(bars):,}`",
        f"- Density rule: at least one predeclared entry-grid row per variant must reach >= {MIN_SIGNALS_PER_YEAR:.0f} signals/year on both full data and limited core",
        f"- Density rows passing: {int(detail['density_gate_pass'].sum())}/{len(detail)}",
        f"- Variants passing the density gate: {int(summary['density_gate_pass'].sum())}/{len(summary)}",
        "",
        "| variant | pass rows | best full signals | best full/year | best limited signals | best limited/year | verdict |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary.to_dict("records"):
        lines.append(
            "| {variant_id} | {passing_entry_rows} | {best_full_signals} | "
            "{best_full_trades_per_year:.2f} | {best_limited_core_signals} | "
            "{best_limited_core_trades_per_year:.2f} | {verdict} |".format(**row)
        )
    lines.append("")
    if verdict == "FAIL":
        lines.append("Conclusion: reject before staged PnL. Do not remove sparse variants or loosen the density rule without an explicit rescue authorization.")
    else:
        lines.append("Conclusion: density is sufficient to proceed to preflight and staged validation. This is not evidence of profitability.")
    return "\n".join(lines) + "\n"


def _iso_or_blank(value: pd.Timestamp | None) -> str:
    return "" if value is None else pd.Timestamp(value).isoformat()


class _AuditRow(dict):
    def __init__(self, columns: list[str], values: tuple, name: int):
        super().__init__(zip(columns, values, strict=True))
        self.name = name


if __name__ == "__main__":
    main()
