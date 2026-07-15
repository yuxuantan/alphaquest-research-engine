from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from propstack.utils.hashing import file_sha256


DEFAULT_INPUT = Path(
    "data/reports/data_quality/ES/"
    "databento_sierra_tick_comparison_0930_1100_20250714_20260610/minute_comparison.csv"
)
DEFAULT_OUTPUT = Path(
    "data/cache/orderflow/es_databento_trades_1m_20250714_20260610_0930_1100_ny.parquet"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize exact Databento 1-minute morning bars from tick audit.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def build_cache(source: pd.DataFrame) -> pd.DataFrame:
    fields = ["open", "high", "low", "close", "volume", "buy_volume", "sell_volume", "signed_volume", "events"]
    required = {"session_date", "contract", "minute", *(f"{field}_db" for field in fields)}
    missing = sorted(required - set(source.columns))
    if missing:
        raise ValueError(f"Databento minute comparison is missing fields: {missing}")
    out = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(source["minute"], utc=True).dt.tz_convert("America/New_York"),
            "session_date": source["session_date"].astype(str),
            "symbol": "ES",
            "contract_symbol": source["contract"].astype(str),
            **{field if field != "events" else "trades": source[f"{field}_db"] for field in fields},
        }
    )
    out["large_record_source_semantics"] = "not_materialized_use_event_stream"
    return out.sort_values("timestamp").reset_index(drop=True)


def main() -> None:
    args = parse_args()
    cache = build_cache(pd.read_csv(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cache.to_parquet(args.output, index=False, compression="zstd")
    metadata = {
        "verdict": "PASS",
        "source": str(args.input),
        "source_sha256": file_sha256(args.input),
        "output": str(args.output),
        "rows": int(len(cache)),
        "sessions": int(cache["session_date"].nunique()),
        "start": str(cache["timestamp"].min()),
        "end": str(cache["timestamp"].max()),
        "event_semantics": "Databento trade messages aggregated after active-contract filtering",
        "large_trade_fields": "not materialized; replay canonical event stream",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    args.output.with_suffix(".validation.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {args.output}: {len(cache)} rows, {cache['session_date'].nunique()} sessions")


if __name__ == "__main__":
    main()
