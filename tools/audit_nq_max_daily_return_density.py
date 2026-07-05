from __future__ import annotations

from pathlib import Path

import pandas as pd


FEATURE_CSV = Path("data/external/nq_max_daily_return_features_20110103_20260612.csv")
DETAIL_CSV = Path("research_artifacts/nq_max_daily_return_lottery_reversal_density_audit_20260701.csv")
SUMMARY_CSV = Path("research_artifacts/nq_max_daily_return_lottery_reversal_density_summary_20260701.csv")
REPORT_MD = Path("research_artifacts/nq_max_daily_return_lottery_reversal_density_audit_20260701.md")

THRESHOLDS = [0.35, 0.45, 0.5]
MIN_SIGNALS_PER_YEAR = 50.0

VARIANTS = [
    {
        "variant_id": "high_5d_max_fade_short_1000",
        "rank_column": "max_return_5d_rank_252",
        "value_column": "prior_max_return_5d",
        "direction_mode": "high_short",
    },
    {
        "variant_id": "high_20d_max_fade_short_1130",
        "rank_column": "max_return_20d_rank_252",
        "value_column": "prior_max_return_20d",
        "direction_mode": "high_short",
    },
    {
        "variant_id": "high_63d_max_fade_short_1200",
        "rank_column": "max_return_63d_rank_252",
        "value_column": "prior_max_return_63d",
        "direction_mode": "high_short",
    },
    {
        "variant_id": "low_5d_max_carry_long_1030",
        "rank_column": "max_return_5d_rank_252",
        "value_column": "prior_max_return_5d",
        "direction_mode": "low_long",
    },
    {
        "variant_id": "high_avg_top5_20d_fade_short_1430",
        "rank_column": "avg_top5_return_20d_rank_252",
        "value_column": "prior_avg_top5_return_20d",
        "direction_mode": "high_short",
    },
]

WINDOWS = {
    "full": ("2011-01-03", "2026-06-12"),
    "limited_core": ("2011-02-22", "2012-09-07"),
    "latest_252": (None, "2026-06-12"),
}


def audit() -> tuple[pd.DataFrame, pd.DataFrame]:
    features = pd.read_csv(FEATURE_CSV, parse_dates=["session_date"])
    latest_start = features["session_date"].sort_values().iloc[-252]
    windows = {
        key: (pd.Timestamp(start) if start else latest_start, pd.Timestamp(end))
        for key, (start, end) in WINDOWS.items()
    }
    detail_rows = []
    for variant in VARIANTS:
        for threshold in THRESHOLDS:
            mask = _mask(features[variant["rank_column"]], variant["direction_mode"], threshold)
            for window_name, (start, end) in windows.items():
                window = features[(features["session_date"] >= start) & (features["session_date"] <= end)]
                count = int(mask.loc[window.index].sum())
                years = len(window) / 252.0
                signals_per_year = count / years if years else 0.0
                detail_rows.append(
                    {
                        "variant_id": variant["variant_id"],
                        "rank_column": variant["rank_column"],
                        "value_column": variant["value_column"],
                        "direction_mode": variant["direction_mode"],
                        "max_rank_threshold": threshold,
                        "window": window_name,
                        "window_start": start.date().isoformat(),
                        "window_end": end.date().isoformat(),
                        "sessions": len(window),
                        "signals": count,
                        "signals_per_year": signals_per_year,
                        "density_pass": signals_per_year >= MIN_SIGNALS_PER_YEAR,
                    }
                )
    detail = pd.DataFrame(detail_rows)
    summary = (
        detail.groupby("variant_id", sort=True)
        .agg(
            entry_rows=("density_pass", "size"),
            rows_passing_density=("density_pass", "sum"),
            min_signals_per_year=("signals_per_year", "min"),
            full_min_signals=("signals", lambda s: int(s[detail.loc[s.index, "window"].eq("full")].min())),
            latest_252_min_signals=("signals", lambda s: int(s[detail.loc[s.index, "window"].eq("latest_252")].min())),
            limited_core_min_signals=(
                "signals",
                lambda s: int(s[detail.loc[s.index, "window"].eq("limited_core")].min()),
            ),
        )
        .reset_index()
    )
    summary["density_gate_pass"] = summary["rows_passing_density"].eq(summary["entry_rows"])

    DETAIL_CSV.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)
    _write_report(detail, summary)
    return detail, summary


def _mask(rank: pd.Series, direction_mode: str, threshold: float) -> pd.Series:
    if direction_mode == "high_short":
        return rank >= 1.0 - threshold
    if direction_mode == "low_long":
        return rank <= threshold
    if direction_mode == "two_sided_extreme":
        return (rank >= 1.0 - threshold) | (rank <= threshold)
    raise ValueError(f"Unsupported direction mode: {direction_mode}")


def _write_report(detail: pd.DataFrame, summary: pd.DataFrame) -> None:
    pass_rows = int(detail["density_pass"].sum())
    total_rows = int(len(detail))
    lines = [
        "# NQ MAX Daily-Return Lottery Reversal Density Audit",
        "",
        "Date: 2026-07-01",
        "",
        f"Verdict: {'PASS' if pass_rows == total_rows else 'FAIL'}",
        "",
        "This is a pre-PnL opportunity-count audit for a strict-prior MAX daily-return state.",
        "The feature CSV maps each NQ session to completed prior-session daily-return MAX metrics only.",
        "",
        f"Rows passing density: {pass_rows}/{total_rows}",
        f"Minimum required signals per year in each window: {MIN_SIGNALS_PER_YEAR}",
        "",
        "## Variant Summary",
        "",
        "| Variant | Rows Passing | Min Signals/Year | Full Min Signals | Limited-Core Min Signals | Latest-252 Min Signals |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary.to_dict("records"):
        lines.append(
            f"| {row['variant_id']} | {int(row['rows_passing_density'])}/{int(row['entry_rows'])} | "
            f"{row['min_signals_per_year']:.2f} | {int(row['full_min_signals'])} | "
            f"{int(row['limited_core_min_signals'])} | {int(row['latest_252_min_signals'])} |"
        )
    lines.extend(
        [
            "",
            "No PnL, stops, targets, or trade outcomes were inspected for this audit.",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    detail, summary = audit()
    print(f"wrote {DETAIL_CSV}")
    print(f"wrote {SUMMARY_CSV}")
    print(f"wrote {REPORT_MD}")
    print(f"pass_rows={int(detail['density_pass'].sum())}/{len(detail)}")
    print(summary[["variant_id", "density_gate_pass", "min_signals_per_year"]].to_string(index=False))


if __name__ == "__main__":
    main()
