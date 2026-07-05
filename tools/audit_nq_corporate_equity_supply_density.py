from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_FEATURES = "data/external/nq_corporate_equity_supply_features_20110103_20260612.csv"
DEFAULT_DETAIL = "research_artifacts/nq_corporate_equity_supply_state_density_audit_20260701.csv"
DEFAULT_SUMMARY = "research_artifacts/nq_corporate_equity_supply_state_density_summary_20260701.csv"
DEFAULT_MARKDOWN = "research_artifacts/nq_corporate_equity_supply_state_density_audit_20260701.md"


VARIANT_GRID = {
    "high_1q_net_equity_short_1000": [
        {
            "column": "net_equity_to_market_1q_rank_40q",
            "tail": "high",
            "supply_rank_threshold": value,
        }
        for value in (0.20, 0.25, 0.30)
    ],
    "high_4q_net_equity_short_1030": [
        {
            "column": "net_equity_to_market_4q_rank_40q",
            "tail": "high",
            "supply_rank_threshold": value,
        }
        for value in (0.20, 0.25, 0.30)
    ],
    "rising_4q_net_equity_short_1130": [
        {
            "column": "net_equity_issuance_4q_change_rank_40q",
            "tail": "high",
            "supply_rank_threshold": value,
        }
        for value in (0.20, 0.25, 0.30)
    ],
    "high_equity_share_short_1200": [
        {
            "column": "equity_financing_share_4q_rank_40q",
            "tail": "high",
            "supply_rank_threshold": value,
        }
        for value in (0.25, 0.30, 0.35)
    ],
    "low_debt_minus_equity_short_1330": [
        {
            "column": "debt_minus_equity_to_market_4q_rank_40q",
            "tail": "low",
            "supply_rank_threshold": value,
        }
        for value in (0.20, 0.25, 0.30)
    ],
}


def audit_density(
    features_csv: str | Path = DEFAULT_FEATURES,
    detail_csv: str | Path = DEFAULT_DETAIL,
    summary_csv: str | Path = DEFAULT_SUMMARY,
    markdown_path: str | Path = DEFAULT_MARKDOWN,
    *,
    min_annual_signals: float = 50.0,
    min_latest_252_signals: int = 50,
    limited_start: str = "2021-07-13",
    limited_end: str = "2022-03-28",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = pd.read_csv(features_csv, parse_dates=["session_date"])
    features = features.sort_values("session_date", kind="mergesort").reset_index(drop=True)
    full_years = len(features) / 252.0
    limited = features[
        (features["session_date"] >= pd.Timestamp(limited_start))
        & (features["session_date"] <= pd.Timestamp(limited_end))
    ].copy()
    limited_years = len(limited) / 252.0
    latest = features.tail(252).copy()

    rows: list[dict] = []
    for variant_id, grid_rows in VARIANT_GRID.items():
        for entry_index, spec in enumerate(grid_rows, start=1):
            full_mask = _mask(features, spec)
            limited_mask = _mask(limited, spec)
            latest_mask = _mask(latest, spec)
            full_count = int(full_mask.sum())
            limited_count = int(limited_mask.sum())
            latest_count = int(latest_mask.sum())
            full_annual = full_count / full_years if full_years else 0.0
            limited_annual = limited_count / limited_years if limited_years else 0.0
            passed = (
                full_annual >= min_annual_signals
                and limited_annual >= min_annual_signals
                and latest_count >= min_latest_252_signals
            )
            rows.append(
                {
                    "variant_id": variant_id,
                    "entry_grid_row": entry_index,
                    "driver_column": spec["column"],
                    "tail": spec["tail"],
                    "supply_rank_threshold": spec["supply_rank_threshold"],
                    "full_signals": full_count,
                    "full_signals_per_year": full_annual,
                    "limited_signals": limited_count,
                    "limited_signals_per_year": limited_annual,
                    "latest_252_signals": latest_count,
                    "pass_density": passed,
                }
            )
    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby("variant_id", as_index=False)
        .agg(
            declared_entry_rows=("entry_grid_row", "count"),
            passing_entry_rows=("pass_density", "sum"),
            min_full_signals_per_year=("full_signals_per_year", "min"),
            min_limited_signals_per_year=("limited_signals_per_year", "min"),
            min_latest_252_signals=("latest_252_signals", "min"),
        )
        .sort_values("variant_id", kind="mergesort")
    )
    summary["variant_pass_density"] = summary["declared_entry_rows"] == summary[
        "passing_entry_rows"
    ]

    detail_path = Path(detail_csv)
    summary_path = Path(summary_csv)
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)
    _write_markdown(markdown_path, detail, summary, features_csv=features_csv)
    return detail, summary


def _mask(frame: pd.DataFrame, spec: dict) -> pd.Series:
    series = pd.to_numeric(frame[spec["column"]], errors="coerce")
    threshold = float(spec["supply_rank_threshold"])
    if spec["tail"] == "high":
        return (series >= 1.0 - threshold).fillna(False)
    if spec["tail"] == "low":
        return (series <= threshold).fillna(False)
    raise ValueError(f"Unsupported tail: {spec['tail']}")


def _write_markdown(
    markdown_path: str | Path,
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    features_csv: str | Path,
) -> None:
    passing_rows = int(detail["pass_density"].sum())
    total_rows = int(len(detail))
    passing_variants = int(summary["variant_pass_density"].sum())
    total_variants = int(len(summary))
    verdict = "PASS" if passing_rows == total_rows and passing_variants == total_variants else "FAIL"
    lines = [
        "# NQ Corporate Equity Supply State Density Audit",
        "",
        f"Verdict: {verdict}.",
        "",
        "No PnL or trade outcomes were inspected. This audit only counts sessions where the predeclared lagged corporate equity supply state would allow a fixed-time NQ signal.",
        "",
        f"Feature CSV: `{features_csv}`",
        "Annualized full/limited-window threshold: 50.00 signals/year.",
        "Latest-252-session threshold: 50 signals.",
        "Limited-core proxy window: 2021-07-13 through 2022-03-28.",
        "",
        f"Passing entry rows: {passing_rows}/{total_rows}.",
        f"Passing variants: {passing_variants}/{total_variants}.",
        "",
        "## Variant Summary",
        "",
        _markdown_table(summary),
        "",
    ]
    Path(markdown_path).write_text("\n".join(lines), encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in frame.iterrows():
        values = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:.6f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", default=DEFAULT_FEATURES)
    parser.add_argument("--detail-csv", default=DEFAULT_DETAIL)
    parser.add_argument("--summary-csv", default=DEFAULT_SUMMARY)
    parser.add_argument("--markdown", default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    detail, summary = audit_density(args.features, args.detail_csv, args.summary_csv, args.markdown)
    print(f"wrote {args.detail_csv}")
    print(f"wrote {args.summary_csv}")
    print(f"wrote {args.markdown}")
    print(f"pass_rows={int(detail['pass_density'].sum())}/{len(detail)}")
    print(f"passing_variants={int(summary['variant_pass_density'].sum())}/{len(summary)}")


if __name__ == "__main__":
    main()
