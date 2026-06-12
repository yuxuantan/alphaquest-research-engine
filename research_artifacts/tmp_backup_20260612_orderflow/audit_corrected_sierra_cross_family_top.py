from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


CROSS_PATH = Path("/private/tmp/corrected_sierra_cross_family_combo_fast.py")
TOP_COMBO = Path("/private/tmp/corrected_sierra_cross_family_combo_fast_top.csv")
OUT_TRADES = Path("/private/tmp/corrected_sierra_cross_family_top_trades.csv")
OUT_ANNUAL = Path("/private/tmp/corrected_sierra_cross_family_top_annual.csv")
OUT_MONTHLY = Path("/private/tmp/corrected_sierra_cross_family_top_monthly.csv")
OUT_LOO = Path("/private/tmp/corrected_sierra_cross_family_top_leave_one_year_out.csv")
OUT_COST = Path("/private/tmp/corrected_sierra_cross_family_top_cost_stress.csv")


spec = importlib.util.spec_from_file_location("crossfast", CROSS_PATH)
cross = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(cross)
vc = cross.vc
pc = cross.pc


def metrics(trades: pd.DataFrame, extra_cost: float = 0.0) -> dict:
    t = trades.copy()
    if extra_cost:
        t["pnl"] = t["pnl"] - extra_cost
    return vc.metric_frame(t)


def rebuild_trades(combo_id: str) -> pd.DataFrame:
    df = pd.read_parquet(vc.SOURCE)
    dates, data, minutes = vc.matrices(df)

    vc.ENTRY_TIMES = ["10:00", "11:00", "13:30", "14:30", "15:00"]
    vc.WINDOWS = [15, 30, 60]
    vc.HOLDS = [60, 120, 180]
    snap_v = vc.build_snapshots(dates, data, minutes)
    vol_res, vol_trades = vc.screen(snap_v)
    _vol_res, vol_trades = cross.tag_results(vol_res, vol_trades, "volume")

    pc.vcfast.ENTRY_TIMES = ["10:00", "10:30", "11:00", "13:00", "13:30", "14:30", "15:00"]
    pc.vcfast.WINDOWS = [5, 15, 30, 60]
    pc.vcfast.HOLDS = [30, 60, 120]
    snap_p = pc.vcfast.build_snapshots(dates, data, minutes)
    snap_p = pc.add_composition_features(snap_p)
    part_res, part_trades = pc.score_family(snap_p)
    _part_res, part_trades = cross.tag_results(part_res, part_trades, "participation")

    all_trades = {**vol_trades, **part_trades}
    frames = [all_trades[leg_id] for leg_id in combo_id.split("|")]
    out = vc.combine_non_overlap(frames).sort_values(["entry_ts", "exit_ts"]).reset_index(drop=True)
    out["year"] = out["entry_ts"].dt.year
    out["month"] = out["entry_ts"].dt.to_period("M").astype(str)
    return out


def main() -> None:
    top = pd.read_csv(TOP_COMBO).iloc[0]
    combo_id = top["combo_id"]
    print("auditing combo", combo_id, flush=True)
    trades = rebuild_trades(combo_id)
    trades.to_csv(OUT_TRADES, index=False)
    print("trades", len(trades), metrics(trades), flush=True)

    annual_rows = []
    for year, group in trades.groupby("year"):
        row = {"year": year, **metrics(group)}
        annual_rows.append(row)
    annual = pd.DataFrame(annual_rows)
    annual.to_csv(OUT_ANNUAL, index=False)
    print("annual", annual[["year", "n", "net", "pf", "max_dd", "worst_day"]].to_string(index=False), flush=True)

    monthly = trades.groupby("month")["pnl"].agg(["count", "sum"]).reset_index()
    monthly.to_csv(OUT_MONTHLY, index=False)

    loo_rows = []
    for year in sorted(trades["year"].unique()):
        subset = trades[trades["year"] != year]
        row = {"excluded_year": int(year), **metrics(subset)}
        loo_rows.append(row)
    loo = pd.DataFrame(loo_rows)
    loo.to_csv(OUT_LOO, index=False)
    print(
        "loo worst",
        loo.sort_values(["net"]).head(5)[["excluded_year", "n", "net", "pf", "cagr", "mar", "max_dd_pct", "early_net", "mid_net", "late_net", "holdout_net"]].to_string(index=False),
        flush=True,
    )

    cost_rows = []
    for extra in [0.0, 6.25, 12.50, 25.00, 50.00]:
        row = {"extra_round_turn_cost": extra, **metrics(trades, extra_cost=extra)}
        row["all_splits_positive"] = all(row[k] > 0 for k in ["early_net", "mid_net", "late_net", "holdout_net"])
        row["acceptance_shaped"] = (
            row["n"] >= 500
            and row["pf"] >= 1.50
            and row["cagr"] >= 0.04
            and row["mar"] >= 0.50
            and row["max_dd_pct"] <= 0.05
            and row["positive_month_rate"] >= 0.50
            and row["worst_day"] >= -4000
            and row["all_splits_positive"]
        )
        cost_rows.append(row)
    cost = pd.DataFrame(cost_rows)
    cost.to_csv(OUT_COST, index=False)
    print(
        "cost",
        cost[["extra_round_turn_cost", "n", "net", "pf", "cagr", "mar", "max_dd_pct", "worst_day", "positive_month_rate", "early_net", "mid_net", "late_net", "holdout_net", "acceptance_shaped"]].to_string(index=False),
        flush=True,
    )


if __name__ == "__main__":
    main()
