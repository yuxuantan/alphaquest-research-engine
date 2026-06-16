from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from propstack.data.es_nq_lead_lag import build_es_nq_lead_lag_cache


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an ES trading cache with completed NQ lead-lag features.")
    parser.add_argument(
        "--es",
        default="data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet",
        help="ES source parquet/CSV path.",
    )
    parser.add_argument(
        "--nq",
        default="data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet",
        help="NQ source parquet/CSV path.",
    )
    parser.add_argument(
        "--out",
        default="data/cache/orderflow/es_nq_lead_lag_1m_20110103_20260609_full_rth_ny.parquet",
        help="Output parquet path.",
    )
    parser.add_argument("--csv-out", help="Optional output CSV path.")
    parser.add_argument("--windows", default="5,15,30,60", help="Comma-separated rolling windows in minutes.")
    args = parser.parse_args()

    windows = [int(item.strip()) for item in args.windows.split(",") if item.strip()]
    build_es_nq_lead_lag_cache(
        es_path=args.es,
        nq_path=args.nq,
        output_parquet=args.out,
        output_csv=args.csv_out,
        windows=windows,
        status_callback=print,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
