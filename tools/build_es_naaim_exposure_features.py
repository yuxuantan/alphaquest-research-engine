from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_NAAIM_INPUT = "data/external/naaim_exposure_index_20260610.xlsx"
DEFAULT_OUTPUT = "data/external/es_naaim_exposure_features_20110103_20260609.csv"

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    naaim_input: str | Path = DEFAULT_NAAIM_INPUT,
    availability_lag_business_days: int = 2,
    start_date: str = "2011-01-03",
    end_date: str = "2026-06-09",
    rank_window: int = 104,
    rank_min_periods: int = 26,
    ma_window: int = 26,
) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp"])
    sessions = (
        pd.DataFrame({"session_date": pd.to_datetime(bars["timestamp"]).dt.date.astype(str)})
        .drop_duplicates("session_date")
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions = sessions[(sessions["session_date"] >= start_date) & (sessions["session_date"] <= end_date)]
    naaim = parse_naaim_xlsx(naaim_input)
    out = build_session_features(
        sessions,
        naaim,
        availability_lag_business_days=availability_lag_business_days,
        rank_window=rank_window,
        rank_min_periods=rank_min_periods,
        ma_window=ma_window,
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def parse_naaim_xlsx(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    with ZipFile(path) as zf:
        shared_strings = _read_shared_strings(zf)
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
    rows: list[dict[int, object]] = []
    for row in sheet.find(f"{_NS}sheetData").findall(f"{_NS}row"):
        values: dict[int, object] = {}
        for cell in row.findall(f"{_NS}c"):
            value_node = cell.find(f"{_NS}v")
            if value_node is None:
                continue
            value = value_node.text
            if cell.attrib.get("t") == "s":
                parsed: object = shared_strings[int(value)]
            else:
                try:
                    parsed = float(value)
                except (TypeError, ValueError):
                    parsed = value
            values[_column_index(cell.attrib.get("r", ""))] = parsed
        if values:
            rows.append(values)
    if not rows:
        raise ValueError(f"NAAIM workbook has no rows: {path}")
    header = [str(rows[0].get(i, "")).strip() for i in range(max(rows[0]) + 1)]
    records = []
    for values in rows[1:]:
        record = {header[i]: values.get(i) for i in range(len(header))}
        if record.get("Date") is None:
            continue
        records.append(
            {
                "observation_date": _excel_date(record["Date"]),
                "naaim_number": _float(record.get("NAAIM Number")),
                "mean_average": _float(record.get("Mean/Average")),
                "quartile_1": _float(record.get("Quart 1 (25% at/below)")),
                "median": _float(record.get("Quart 2 (median)")),
                "quartile_3": _float(record.get("Quart 3 (25% at/above)")),
                "standard_deviation": _float(record.get("Standard Deviation")),
                "sp500": _float(record.get("S&P 500")),
            }
        )
    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError(f"NAAIM workbook has no parseable observations: {path}")
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df = (
        df.dropna(subset=["observation_date", "naaim_number"])
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )
    return df


def build_session_features(
    sessions: pd.DataFrame,
    naaim: pd.DataFrame,
    *,
    availability_lag_business_days: int = 2,
    rank_window: int = 104,
    rank_min_periods: int = 26,
    ma_window: int = 26,
) -> pd.DataFrame:
    if availability_lag_business_days < 0:
        raise ValueError("availability_lag_business_days must be non-negative.")
    sessions = sessions.copy()
    sessions["session_date"] = pd.to_datetime(sessions["session_date"]).dt.date.astype(str)
    session_dates = pd.to_datetime(sessions["session_date"])
    naaim = naaim.copy().sort_values("observation_date", kind="mergesort").reset_index(drop=True)
    naaim["observation_date"] = pd.to_datetime(naaim["observation_date"])
    naaim["availability_date"] = naaim["observation_date"] + pd.offsets.BDay(availability_lag_business_days)
    naaim["naaim_change_1w"] = naaim["naaim_number"] - naaim["naaim_number"].shift(1)
    naaim["naaim_change_4w"] = naaim["naaim_number"] - naaim["naaim_number"].shift(4)
    naaim[f"naaim_rank_{rank_window}"] = _rolling_last_percentile(
        naaim["naaim_number"],
        rank_window,
        rank_min_periods,
    )
    naaim[f"naaim_change_rank_{rank_window}"] = _rolling_last_percentile(
        naaim["naaim_change_1w"],
        rank_window,
        rank_min_periods,
    )
    rolling = naaim["naaim_number"].rolling(rank_window, min_periods=rank_min_periods)
    naaim[f"naaim_median_{rank_window}"] = rolling.median()
    naaim[f"naaim_mean_{rank_window}"] = rolling.mean()
    naaim[f"naaim_std_{rank_window}"] = rolling.std(ddof=0)
    naaim[f"naaim_z_{rank_window}"] = (
        naaim["naaim_number"] - naaim[f"naaim_mean_{rank_window}"]
    ) / naaim[f"naaim_std_{rank_window}"].replace(0.0, pd.NA)
    naaim[f"naaim_ma_{ma_window}"] = naaim["naaim_number"].rolling(ma_window, min_periods=rank_min_periods).mean()
    naaim[f"naaim_vs_ma_{ma_window}"] = naaim["naaim_number"] - naaim[f"naaim_ma_{ma_window}"]

    signal_sessions = []
    for _, row in naaim.iterrows():
        candidates = sessions[session_dates >= row["availability_date"].normalize()]
        signal_sessions.append(candidates.iloc[0]["session_date"] if not candidates.empty else None)
    naaim["session_date"] = signal_sessions
    naaim = naaim.dropna(subset=["session_date"]).drop_duplicates("session_date", keep="last")
    out = sessions.merge(naaim, on="session_date", how="inner").sort_values("session_date", kind="mergesort")
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)
    out["availability_date"] = pd.to_datetime(out["availability_date"]).dt.date.astype(str)
    columns = [
        "session_date",
        "observation_date",
        "availability_date",
        "naaim_number",
        "mean_average",
        "quartile_1",
        "median",
        "quartile_3",
        "standard_deviation",
        "sp500",
        "naaim_change_1w",
        "naaim_change_4w",
        f"naaim_rank_{rank_window}",
        f"naaim_change_rank_{rank_window}",
        f"naaim_median_{rank_window}",
        f"naaim_mean_{rank_window}",
        f"naaim_std_{rank_window}",
        f"naaim_z_{rank_window}",
        f"naaim_ma_{ma_window}",
        f"naaim_vs_ma_{ma_window}",
    ]
    return out[columns].reset_index(drop=True)


def _read_shared_strings(zf: ZipFile) -> list[str]:
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall(f"{_NS}si"):
        strings.append("".join(text.text or "" for text in item.iter(f"{_NS}t")))
    return strings


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in str(cell_ref) if ch.isalpha())
    out = 0
    for char in letters:
        out = out * 26 + ord(char.upper()) - 64
    return out - 1


def _excel_date(value) -> pd.Timestamp:
    return pd.Timestamp("1899-12-30") + pd.to_timedelta(float(value), unit="D")


def _float(value) -> float:
    return float(value) if value not in {None, ""} else float("nan")


def _rolling_last_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def percentile(values) -> float:
        clean = pd.Series(values).dropna()
        if clean.empty:
            return float("nan")
        return float(clean.rank(pct=True, method="average").iloc[-1])

    return series.rolling(window, min_periods=min_periods).apply(percentile, raw=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build futures session features from the public NAAIM Exposure Index workbook.")
    parser.add_argument("--bars-input", default=DEFAULT_BARS_INPUT)
    parser.add_argument("--naaim-input", default=DEFAULT_NAAIM_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--availability-lag-business-days", type=int, default=2)
    parser.add_argument("--start-date", default="2011-01-03")
    parser.add_argument("--end-date", default="2026-06-09")
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        naaim_input=args.naaim_input,
        availability_lag_business_days=args.availability_lag_business_days,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    print(
        f"Wrote {len(features)} NAAIM signal sessions to {args.output} "
        f"({features['session_date'].min()} -> {features['session_date'].max()})."
    )


if __name__ == "__main__":
    main()
