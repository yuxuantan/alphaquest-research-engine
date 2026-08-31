"""Build compact, hash-bound ETH ATR seeds for the adaptive Yush strategy.

The execution lane begins at 09:30 America/New_York, so it cannot derive an
ATR14 at the open from its own RTH events.  This tool uses the governed,
explicit-roll one-minute OHLCV history to freeze the last fourteen completed
three-minute true ranges before each eligible session open.  Runtime mechanics
then update the seed with completed RTH three-minute bars only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_SOURCE = Path(
    "data/cache/databento/"
    "es_databento_ohlcv_1m_20100606_20260531_eth_rth_explicit_roll.parquet"
)
DEFAULT_SESSIONS = Path(
    "research/datasets/"
    "es_sierra_yush_events_20110815_20260529_0930_1100_ny_inv02/"
    "bars.parquet"
)
DEFAULT_OUTPUT = Path(
    "research/datasets/"
    "es_sierra_yush_events_20110815_20260529_0930_1100_ny_inv02/"
    "atr14_3m_eth_context.parquet"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--sessions", type=Path, default=DEFAULT_SESSIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--lookback", type=int, default=14)
    args = parser.parse_args()
    if args.lookback < 2:
        raise ValueError("ATR lookback must be at least two bars")

    source = pd.read_parquet(
        args.source,
        columns=["timestamp", "open", "high", "low", "close", "contract_symbol"],
    )
    timestamps = pd.to_datetime(source["timestamp"], utc=True).dt.tz_convert(
        "America/New_York"
    )
    source = source.assign(timestamp=timestamps).sort_values(
        ["contract_symbol", "timestamp"],
        kind="mergesort",
    )
    three_minute = (
        source.set_index("timestamp")
        .groupby("contract_symbol", sort=False)
        .resample("3min", origin="start_day")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
        )
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )
    previous_close = three_minute.groupby("contract_symbol", sort=False)[
        "close"
    ].shift(1)
    three_minute["true_range"] = np.maximum.reduce(
        [
            three_minute["high"] - three_minute["low"],
            (three_minute["high"] - previous_close).abs(),
            (three_minute["low"] - previous_close).abs(),
        ]
    )

    sessions = pd.read_parquet(
        args.sessions,
        columns=["timestamp", "contract_symbol"],
    )
    session_timestamps = pd.to_datetime(sessions["timestamp"], utc=True).dt.tz_convert(
        "America/New_York"
    )
    sessions = sessions.assign(
        timestamp=session_timestamps,
        session_date=session_timestamps.dt.date.astype(str),
    )
    session_contracts = (
        sessions.sort_values("timestamp", kind="mergesort")
        .drop_duplicates("session_date", keep="first")
        [["session_date", "contract_symbol"]]
    )
    session_contracts["source_contract_symbol"] = session_contracts[
        "contract_symbol"
    ].map(_databento_contract_symbol)

    bars_by_contract = {
        str(contract): frame.reset_index(drop=True)
        for contract, frame in three_minute.groupby("contract_symbol", sort=False)
    }
    records: list[dict[str, object]] = []
    for row in session_contracts.itertuples(index=False):
        session_date = str(row.session_date)
        contract = str(row.contract_symbol)
        source_contract = str(row.source_contract_symbol)
        bars = bars_by_contract.get(source_contract)
        if bars is None:
            continue
        open_timestamp = pd.Timestamp(
            f"{session_date} 09:30:00",
            tz="America/New_York",
        )
        completed = bars.loc[
            bars["timestamp"] + pd.Timedelta(minutes=3) <= open_timestamp
        ].tail(args.lookback)
        completed = completed.loc[completed["true_range"].notna()]
        if len(completed) != args.lookback:
            continue
        last = completed.iloc[-1]
        records.append(
            {
                "session_date": session_date,
                "contract_symbol": contract,
                "source_contract_symbol": source_contract,
                "atr_lookback_bars": int(args.lookback),
                "atr14_3m_seed_points": float(completed["true_range"].mean()),
                "previous_close_points": float(last["close"]),
                "last_seed_bar_open": pd.Timestamp(last["timestamp"]),
                "last_seed_bar_close": pd.Timestamp(last["timestamp"])
                + pd.Timedelta(minutes=3),
            }
        )

    output = pd.DataFrame.from_records(records)
    if output.empty:
        raise ValueError("ATR context build produced no eligible sessions")
    expected = set(session_contracts["session_date"].astype(str))
    actual = set(output["session_date"].astype(str))
    missing = sorted(expected - actual)
    if missing:
        raise ValueError(
            f"ATR context is missing {len(missing)} governed session(s); first={missing[:5]}"
        )
    output = output.sort_values("session_date", kind="mergesort").reset_index(drop=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(args.output, index=False)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "schema": "alphaquest.yush-atr-context/v1",
                "source": str(args.source),
                "sessions": str(args.sessions),
                "output": str(args.output),
                "rows": int(len(output)),
                "coverage_start": str(output["session_date"].min()),
                "coverage_end": str(output["session_date"].max()),
                "lookback_bars": int(args.lookback),
                "sha256": digest,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _databento_contract_symbol(value: object) -> str:
    """Map Sierra's two-digit year to Databento's one-digit futures symbol."""

    text = str(value)
    if len(text) < 2 or not text[-2:].isdigit():
        raise ValueError(f"unsupported futures contract symbol: {text!r}")
    return f"{text[:-2]}{text[-1]}"


if __name__ == "__main__":
    main()
