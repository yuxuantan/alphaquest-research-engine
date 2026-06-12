from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


VC_PATH = Path("/private/tmp/corrected_sierra_volume_curve_flow_fast.py")
PC_PATH = Path("/private/tmp/corrected_sierra_participation_composition_fast.py")
OUT_ALL = Path("/private/tmp/corrected_sierra_cross_family_combo_fast_all.csv")
OUT_TOP = Path("/private/tmp/corrected_sierra_cross_family_combo_fast_top.csv")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


vc = load_module(VC_PATH, "vcfast")
pc = load_module(PC_PATH, "pcfast")


def tag_results(res: pd.DataFrame, trades_by_leg: dict[str, pd.DataFrame], prefix: str) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    tagged = res.copy()
    tagged["source_family"] = prefix
    tagged["source_leg_id"] = tagged["leg_id"]
    tagged["leg_id"] = prefix + "::" + tagged["leg_id"].astype(str)
    tagged_trades = {}
    for old_id, trades in trades_by_leg.items():
        new_id = prefix + "::" + old_id
        t = trades.copy()
        t["leg_id"] = new_id
        tagged_trades[new_id] = t
    return tagged, tagged_trades


def gates(row: dict) -> dict[str, bool]:
    return {
        "n": row["n"] >= 500,
        "pf": row["pf"] >= 1.50,
        "cagr": row["cagr"] >= 0.04,
        "mar": row["mar"] >= 0.50,
        "dd": row["max_dd_pct"] <= 0.05,
        "pm": row["positive_month_rate"] >= 0.50,
        "worst": row["worst_day"] >= -4000,
        "splits": row["all_splits_positive"],
    }


def combo_beam(candidates: pd.DataFrame, trades_by_leg: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    beams = [([], None, {"score": 0.0})]
    seen = set()
    for depth in range(1, 8):
        next_beams = []
        for leg_ids, trades, _score_row in beams:
            for leg_id in candidates["leg_id"]:
                if leg_id in leg_ids:
                    continue
                ids = [*leg_ids, leg_id]
                key = tuple(sorted(ids))
                if key in seen:
                    continue
                seen.add(key)
                combo_trades = trades_by_leg[leg_id] if trades is None else vc.combine_non_overlap([trades, trades_by_leg[leg_id]])
                m = vc.metric_frame(combo_trades)
                if m["n"] < 250 or m["net"] <= 0:
                    continue
                all_splits = all(m[k] > 0 for k in ["early_net", "mid_net", "late_net", "holdout_net"])
                m["combo_id"] = "|".join(ids)
                m["legs"] = len(ids)
                m["families"] = ",".join(sorted({i.split("::", 1)[0] for i in ids}))
                m["all_splits_positive"] = all_splits
                g = gates(m)
                m["gate_count"] = int(sum(g.values()))
                m["loose"] = m["n"] >= 500 and m["pf"] >= 1.25 and m["max_dd_pct"] <= 0.08 and all_splits
                m["acceptance_shaped"] = all(g.values())
                m["score"] = (
                    m["net"] / 10_000
                    + min(m["pf"], 3.0)
                    + min(m["mar"], 3.0)
                    - m["max_dd_pct"] * 20
                    + int(all_splits)
                    + np.log1p(m["n"]) / 5
                    + 0.5 * int("," in m["families"])
                )
                rows.append(m)
                next_beams.append((ids, combo_trades, m))
        beams = sorted(next_beams, key=lambda x: x[2]["score"], reverse=True)[:100]
        print(f"depth={depth} beams={len(beams)} rows={len(rows)}", flush=True)
        if not beams:
            break
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["acceptance_shaped", "gate_count", "score"], ascending=[False, False, False])
    return out


def main() -> None:
    print(f"loading {vc.SOURCE}", flush=True)
    df = pd.read_parquet(vc.SOURCE)
    print(f"loaded rows={len(df):,}", flush=True)
    dates, data, minutes = vc.matrices(df)
    print(f"sessions={len(dates):,} minutes={len(minutes):,}", flush=True)

    vc.ENTRY_TIMES = ["10:00", "11:00", "13:30", "14:30", "15:00"]
    vc.WINDOWS = [15, 30, 60]
    vc.HOLDS = [60, 120, 180]
    snap_v = vc.build_snapshots(dates, data, minutes)
    vol_res, vol_trades = vc.screen(snap_v)
    print(f"volume legs={len(vol_res):,}", flush=True)

    pc.vcfast.ENTRY_TIMES = ["10:00", "10:30", "11:00", "13:00", "13:30", "14:30", "15:00"]
    pc.vcfast.WINDOWS = [5, 15, 30, 60]
    pc.vcfast.HOLDS = [30, 60, 120]
    snap_p = pc.vcfast.build_snapshots(dates, data, minutes)
    snap_p = pc.add_composition_features(snap_p)
    part_res, part_trades = pc.score_family(snap_p)
    print(f"participation legs={len(part_res):,}", flush=True)

    vol_res, vol_trades = tag_results(vol_res, vol_trades, "volume")
    part_res, part_trades = tag_results(part_res, part_trades, "participation")
    all_trades = {**vol_trades, **part_trades}

    pool = pd.concat([vol_res, part_res], ignore_index=True)
    pool = pool[(pool["net"] > 0) & (pool["n"] >= 50)].copy()
    pool["candidate_score"] = (
        pool["score"]
        + (pool["n"] >= 120).astype(int)
        + pool["all_splits_positive"].astype(int)
        + (pool["pf"] >= 1.5).astype(int)
    )
    candidates = (
        pool.sort_values(["candidate_score", "score"], ascending=[False, False])
        .groupby("source_family", group_keys=False)
        .head(18)
        .sort_values(["candidate_score", "score"], ascending=[False, False])
    )
    print("candidate legs", len(candidates), candidates["source_family"].value_counts().to_dict(), flush=True)
    combo = combo_beam(candidates, all_trades)
    combo.to_csv(OUT_ALL, index=False)
    combo.head(100).to_csv(OUT_TOP, index=False)
    if combo.empty:
        print("no combo rows", flush=True)
        return
    print(
        f"combo rows={len(combo):,} acceptance={int(combo['acceptance_shaped'].sum())} "
        f"loose={int(combo['loose'].sum())}",
        flush=True,
    )
    print(
        combo.head(15)[
            [
                "combo_id",
                "families",
                "legs",
                "n",
                "net",
                "pf",
                "cagr",
                "mar",
                "max_dd_pct",
                "worst_day",
                "positive_month_rate",
                "early_net",
                "mid_net",
                "late_net",
                "holdout_net",
                "gate_count",
                "acceptance_shaped",
                "loose",
            ]
        ].to_string(index=False),
        flush=True,
    )


if __name__ == "__main__":
    main()
