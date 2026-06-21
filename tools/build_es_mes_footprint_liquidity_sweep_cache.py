from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FOOTPRINT = PROJECT_ROOT / "data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_MES = PROJECT_ROOT / "data/cache/orderflow/es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/cache/orderflow/es_mes_footprint_liquidity_sweep_1m_20190506_20260609_full_rth_ny.parquet"


FOOTPRINT_COLUMNS = [
    "timestamp",
    "symbol",
    "contract_symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "signed_volume",
    "buy_volume",
    "sell_volume",
    "large10_signed_volume",
    "large20_signed_volume",
    "large10_volume",
    "large20_volume",
    "trades",
    "footprint_absorption_long",
    "footprint_absorption_short",
    "footprint_max_sell_imbalance_volume",
    "footprint_max_buy_imbalance_volume",
    "footprint_highest_sell_imbalance_price",
    "footprint_lowest_buy_imbalance_price",
]

MES_COLUMNS = [
    "timestamp",
    "mes_open",
    "mes_high",
    "mes_low",
    "mes_close",
    "mes_volume",
    "mes_signed_volume",
    "mes_buy_volume",
    "mes_sell_volume",
    "mes_large10_signed_volume",
    "mes_large20_signed_volume",
    "mes_large10_volume",
    "mes_large20_volume",
    "mes_trades",
    "mes_participation_share_15",
    "mes_trade_share_15",
    "mes_participation_share_15_rank252",
    "mes_trade_share_15_rank252",
    "mes_participation_share_30",
    "mes_trade_share_30",
    "mes_participation_share_30_rank252",
    "mes_trade_share_30_rank252",
    "mes_trade_orderflow_imbalance_15",
    "mes_trade_orderflow_imbalance_30",
    "mes_trade_orderflow_large10_imbalance_15",
    "mes_trade_orderflow_large10_imbalance_30",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local ES footprint + MES participation cache.")
    parser.add_argument("--footprint", default=DEFAULT_FOOTPRINT)
    parser.add_argument("--mes", default=DEFAULT_MES)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    footprint_path = Path(args.footprint)
    mes_path = Path(args.mes)
    output_path = Path(args.output)
    validation_path = output_path.with_suffix(".validation.json")

    footprint = pd.read_parquet(footprint_path, columns=FOOTPRINT_COLUMNS)
    mes = pd.read_csv(mes_path, usecols=MES_COLUMNS, parse_dates=["timestamp"])
    footprint["timestamp"] = _to_ny_naive(footprint["timestamp"])
    mes["timestamp"] = _to_ny_naive(mes["timestamp"])

    merged = footprint.merge(mes, on="timestamp", how="inner", validate="one_to_one")
    merged = merged.sort_values("timestamp").reset_index(drop=True)
    merged["session_date"] = merged["timestamp"].dt.date.astype(str)
    merged["session_label"] = "RTH"
    merged["is_rth"] = True

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(output_path, index=False)

    validation = {
        "output_parquet": str(output_path.relative_to(PROJECT_ROOT)),
        "source_footprint": str(footprint_path.relative_to(PROJECT_ROOT)),
        "source_mes": str(mes_path.relative_to(PROJECT_ROOT)),
        "rows": int(len(merged)),
        "columns": list(merged.columns),
        "first_timestamp": str(merged["timestamp"].min()),
        "last_timestamp": str(merged["timestamp"].max()),
        "duplicate_timestamps": int(merged["timestamp"].duplicated().sum()),
        "local_only": True,
        "cost_policy": "Built only from existing local Sierra footprint and MES participation caches; no paid data download.",
    }
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


def _to_ny_naive(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series)
    if isinstance(values.dtype, pd.DatetimeTZDtype):
        return values.dt.tz_convert("America/New_York").dt.tz_localize(None)
    return values


if __name__ == "__main__":
    raise SystemExit(main())
