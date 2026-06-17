from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_EQUITY_CACHE = "data/external/cboe_equity_put_call_ratio_2006_2026.csv"
DEFAULT_INDEX_CACHE = "data/external/cboe_index_put_call_ratio_2003_2026.csv"
DEFAULT_TOTAL_CACHE = "data/external/cboe_total_put_call_ratio_2006_2026.csv"
DEFAULT_OUTPUT = "data/external/es_cboe_put_call_features_20110103_20260609.csv"
DEFAULT_EQUITY_URL = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv"
DEFAULT_INDEX_URL = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/indexpcarchive.csv"
DEFAULT_TOTAL_URL = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    equity_input: str | Path | None = None,
    index_input: str | Path | None = None,
    total_input: str | Path | None = None,
    equity_cache: str | Path = DEFAULT_EQUITY_CACHE,
    index_cache: str | Path = DEFAULT_INDEX_CACHE,
    total_cache: str | Path = DEFAULT_TOTAL_CACHE,
    rank_min_periods: int = 60,
) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp"])
    bars = bars.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    sessions = (
        pd.DataFrame({"session_date": pd.to_datetime(bars["timestamp"]).dt.date.astype(str)})
        .drop_duplicates("session_date")
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])

    equity = _load_cboe_pc(
        input_path=equity_input,
        cache_path=equity_cache,
        url=DEFAULT_EQUITY_URL,
        prefix="equity",
    )
    index = _load_cboe_pc(
        input_path=index_input,
        cache_path=index_cache,
        url=DEFAULT_INDEX_URL,
        prefix="index",
    )
    total = _load_cboe_pc(
        input_path=total_input,
        cache_path=total_cache,
        url=DEFAULT_TOTAL_URL,
        prefix="total",
    )
    cboe = (
        equity.merge(index, on="observation_date", how="outer")
        .merge(total, on="observation_date", how="outer")
        .sort_values("observation_date", kind="mergesort")
    )
    value_columns = [column for column in cboe.columns if column != "observation_date"]
    cboe[value_columns] = cboe[value_columns].ffill()
    cboe = cboe.dropna(subset=["equity_pc_ratio", "index_pc_ratio", "total_pc_ratio"])

    # Cboe put/call ratios summarize completed daily options volume.  They are
    # unavailable during that same ES RTH session, so merge strictly to the
    # latest prior Cboe trade date.
    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        cboe.sort_values("observation_date"),
        left_on="session_date_ts",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=False,
    ).sort_values("session_date_ts", kind="mergesort")

    for prefix in ["equity", "index", "total"]:
        merged[f"{prefix}_pc_change_1d"] = merged[f"{prefix}_pc_ratio"] - merged[
            f"{prefix}_pc_ratio"
        ].shift(1)
        merged[f"{prefix}_pc_change_5d"] = merged[f"{prefix}_pc_ratio"] - merged[
            f"{prefix}_pc_ratio"
        ].shift(5)
    merged["index_minus_equity_pc"] = merged["index_pc_ratio"] - merged["equity_pc_ratio"]
    merged["total_minus_equity_pc"] = merged["total_pc_ratio"] - merged["equity_pc_ratio"]

    rank_columns = [
        "equity_pc_ratio",
        "index_pc_ratio",
        "total_pc_ratio",
        "equity_pc_change_1d",
        "index_pc_change_1d",
        "total_pc_change_1d",
        "equity_pc_change_5d",
        "index_pc_change_5d",
        "total_pc_change_5d",
        "index_minus_equity_pc",
        "total_minus_equity_pc",
    ]
    for column in rank_columns:
        merged[f"{column}_rank_252"] = _rolling_last_percentile(
            merged[column], 252, rank_min_periods
        )

    columns = [
        "session_date",
        "observation_date",
        "equity_pc_ratio",
        "index_pc_ratio",
        "total_pc_ratio",
        "equity_call_volume",
        "equity_put_volume",
        "index_call_volume",
        "index_put_volume",
        "total_call_volume",
        "total_put_volume",
        "equity_pc_change_1d",
        "index_pc_change_1d",
        "total_pc_change_1d",
        "equity_pc_change_5d",
        "index_pc_change_5d",
        "total_pc_change_5d",
        "index_minus_equity_pc",
        "total_minus_equity_pc",
        "equity_pc_ratio_rank_252",
        "index_pc_ratio_rank_252",
        "total_pc_ratio_rank_252",
        "equity_pc_change_1d_rank_252",
        "index_pc_change_1d_rank_252",
        "total_pc_change_1d_rank_252",
        "equity_pc_change_5d_rank_252",
        "index_pc_change_5d_rank_252",
        "total_pc_change_5d_rank_252",
        "index_minus_equity_pc_rank_252",
        "total_minus_equity_pc_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_cboe_pc(
    *,
    input_path: str | Path | None,
    cache_path: str | Path,
    url: str,
    prefix: str,
) -> pd.DataFrame:
    if input_path is not None:
        text = Path(input_path).read_text(encoding="utf-8", errors="replace")
    else:
        cache = Path(cache_path)
        if cache.exists():
            text = cache.read_text(encoding="utf-8", errors="replace")
        else:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=30) as response:
                text = response.read().decode("utf-8", errors="replace")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(text, encoding="utf-8")

    rows = text.splitlines()
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if row.lower().startswith("date,") or row.lower().startswith("trade_date,")
        ),
        None,
    )
    if header_index is None:
        raise ValueError(f"Cboe put/call CSV has no data header: {url}")

    raw = pd.read_csv(StringIO("\n".join(rows[header_index:])))
    column_map = {_normalize_column(column): column for column in raw.columns}
    date_col = _required(column_map, "date", "trade date")
    call_col = _required(column_map, "call", "calls")
    put_col = _required(column_map, "put", "puts")
    ratio_col = _required(column_map, "p/c ratio")
    out = raw[[date_col, call_col, put_col, ratio_col]].copy()
    out.columns = [
        "observation_date",
        f"{prefix}_call_volume",
        f"{prefix}_put_volume",
        f"{prefix}_pc_ratio",
    ]
    out["observation_date"] = pd.to_datetime(out["observation_date"], errors="coerce")
    for column in [f"{prefix}_call_volume", f"{prefix}_put_volume", f"{prefix}_pc_ratio"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return (
        out.dropna(subset=["observation_date", f"{prefix}_pc_ratio"])
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _rolling_last_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def percentile(values) -> float:
        clean = pd.Series(values).dropna()
        if clean.empty:
            return float("nan")
        return float(clean.rank(pct=True, method="average").iloc[-1])

    return series.rolling(window, min_periods=min_periods).apply(percentile, raw=False)


def _normalize_column(value: str) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").split())


def _required(column_map: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in column_map:
            return column_map[key]
    raise ValueError(f"Cboe put/call input is missing one of required columns: {keys}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-input", default=DEFAULT_BARS_INPUT)
    parser.add_argument("--equity-input", default=None)
    parser.add_argument("--index-input", default=None)
    parser.add_argument("--total-input", default=None)
    parser.add_argument("--equity-cache", default=DEFAULT_EQUITY_CACHE)
    parser.add_argument("--index-cache", default=DEFAULT_INDEX_CACHE)
    parser.add_argument("--total-cache", default=DEFAULT_TOTAL_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        equity_input=args.equity_input,
        index_input=args.index_input,
        total_input=args.total_input,
        equity_cache=args.equity_cache,
        index_cache=args.index_cache,
        total_cache=args.total_cache,
    )
    valid = features.dropna(
        subset=[
            "equity_pc_ratio_rank_252",
            "equity_pc_change_1d_rank_252",
            "index_pc_change_1d_rank_252",
            "index_minus_equity_pc_rank_252",
        ]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
