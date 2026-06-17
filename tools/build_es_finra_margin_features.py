from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import time
from urllib.request import Request, urlopen
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_MARGIN_CACHE = "data/external/finra_margin_statistics.xlsx"
DEFAULT_OUTPUT = "data/external/es_finra_margin_leverage_features_20110103_20260609.csv"
FINRA_MARGIN_URL = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    margin_input: str | Path | None = None,
    margin_cache: str | Path = DEFAULT_MARGIN_CACHE,
    availability_lag_days: int = 35,
    rank_window_months: int = 120,
    rank_min_periods: int = 36,
) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp"])
    sessions = (
        pd.DataFrame({"session_date": pd.to_datetime(bars["timestamp"]).dt.date.astype(str)})
        .drop_duplicates("session_date")
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])
    sessions["available_observation_cutoff"] = sessions["session_date_ts"] - pd.Timedelta(
        days=availability_lag_days
    )

    margin = _load_margin_stats(margin_input=margin_input, margin_cache=margin_cache)
    margin = _add_margin_features(
        margin,
        rank_window_months=rank_window_months,
        rank_min_periods=rank_min_periods,
    )

    # FINRA margin balances are monthly.  The source has historically updated
    # after month-end, so session D only receives observations at least
    # availability_lag_days old.  This intentionally gives up timeliness to avoid
    # revision/release-date lookahead.
    merged = pd.merge_asof(
        sessions.sort_values("available_observation_cutoff"),
        margin.sort_values("observation_date"),
        left_on="available_observation_cutoff",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")
    merged = merged.drop(columns=["session_date_ts", "available_observation_cutoff"])

    columns = [
        "session_date",
        "observation_date",
        "margin_debt",
        "cash_free_credit",
        "margin_free_credit",
        "total_free_credit",
        "debit_credit_ratio",
        "margin_debt_change_1m",
        "margin_debt_change_3m",
        "margin_debt_change_12m",
        "debit_credit_ratio_change_3m",
        "margin_debt_rank_120m",
        "debit_credit_ratio_rank_120m",
        "margin_debt_change_1m_rank_120m",
        "margin_debt_change_3m_rank_120m",
        "margin_debt_change_12m_rank_120m",
        "debit_credit_ratio_change_3m_rank_120m",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_margin_stats(
    *,
    margin_input: str | Path | None,
    margin_cache: str | Path,
) -> pd.DataFrame:
    if margin_input is not None:
        source = Path(margin_input)
    else:
        source = Path(margin_cache)
        if not source.exists():
            raw = _download_with_retries(FINRA_MARGIN_URL)
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(raw)

    if source.suffix.lower() == ".csv":
        raw = pd.read_csv(source)
    else:
        raw = _read_finra_xlsx(source)

    column_map = {_normalize_column(column): column for column in raw.columns}
    date_col = _first_existing(column_map, ["year month", "year-month", "observation date", "date"])
    debt_col = _first_existing(
        column_map,
        ["debit balances in customers securities margin accounts", "margin debt", "debit balances"],
    )
    cash_col = _first_existing(
        column_map,
        ["free credit balances in customers cash accounts", "cash free credit"],
    )
    margin_credit_col = _first_existing(
        column_map,
        ["free credit balances in customers securities margin accounts", "margin free credit"],
    )
    if not all([date_col, debt_col, cash_col, margin_credit_col]):
        raise ValueError("FINRA margin input is missing required date/debit/free-credit columns.")

    out = raw[[date_col, debt_col, cash_col, margin_credit_col]].copy()
    out.columns = [
        "year_month",
        "margin_debt",
        "cash_free_credit",
        "margin_free_credit",
    ]
    out["observation_date"] = pd.to_datetime(out["year_month"].astype(str) + "-01") + pd.offsets.MonthEnd(0)
    for column in ["margin_debt", "cash_free_credit", "margin_free_credit"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return (
        out[["observation_date", "margin_debt", "cash_free_credit", "margin_free_credit"]]
        .dropna(how="any")
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _read_finra_xlsx(path: Path) -> pd.DataFrame:
    with ZipFile(path) as archive:
        sheet_xml = archive.read("xl/worksheets/sheet1.xml")
    root = ET.fromstring(sheet_xml)
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    records: list[dict[str, str]] = []
    headers: dict[str, str] = {}
    for row in root.findall(".//a:sheetData/a:row", ns):
        cells: dict[str, str] = {}
        for cell in row.findall("a:c", ns):
            ref = cell.attrib.get("r", "")
            col = "".join(ch for ch in ref if ch.isalpha())
            cells[col] = _xlsx_cell_text(cell, ns)
        if row.attrib.get("r") == "1":
            headers = {col: value for col, value in cells.items() if value}
            continue
        if not headers:
            continue
        record = {headers[col]: value for col, value in cells.items() if col in headers}
        if record:
            records.append(record)
    return pd.DataFrame.from_records(records)


def _xlsx_cell_text(cell: ET.Element, ns: dict[str, str]) -> str:
    inline = cell.find("a:is/a:t", ns)
    if inline is not None:
        return inline.text or ""
    value = cell.find("a:v", ns)
    return "" if value is None else (value.text or "")


def _add_margin_features(
    margin: pd.DataFrame,
    *,
    rank_window_months: int,
    rank_min_periods: int,
) -> pd.DataFrame:
    out = margin.copy()
    out["total_free_credit"] = out["cash_free_credit"] + out["margin_free_credit"]
    out["debit_credit_ratio"] = out["margin_debt"] / out["total_free_credit"].replace(0, pd.NA)
    out["margin_debt_change_1m"] = out["margin_debt"].pct_change(1)
    out["margin_debt_change_3m"] = out["margin_debt"].pct_change(3)
    out["margin_debt_change_12m"] = out["margin_debt"].pct_change(12)
    out["debit_credit_ratio_change_3m"] = out["debit_credit_ratio"].pct_change(3)
    for column in [
        "margin_debt",
        "debit_credit_ratio",
        "margin_debt_change_1m",
        "margin_debt_change_3m",
        "margin_debt_change_12m",
        "debit_credit_ratio_change_3m",
    ]:
        out[f"{column}_rank_120m"] = _rolling_last_percentile(
            out[column],
            rank_window_months,
            rank_min_periods,
        )
    return out


def _rolling_last_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def percentile(values) -> float:
        clean = pd.Series(values).dropna()
        if clean.empty:
            return float("nan")
        return float(clean.rank(pct=True, method="average").iloc[-1])

    return series.rolling(window, min_periods=min_periods).apply(percentile, raw=False)


def _download_with_retries(url: str, attempts: int = 4, sleep_seconds: float = 2.0) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=30) as response:
                return response.read()
        except Exception as exc:  # pragma: no cover - network fallback.
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(sleep_seconds * attempt)
    raise RuntimeError(f"Failed to download free FINRA margin file after {attempts} attempts: {url}") from last_error


def _normalize_column(value: str) -> str:
    return " ".join(
        str(value).strip().lower().replace("_", " ").replace("'", "").replace("-", " ").split()
    )


def _first_existing(column_map: dict[str, str], keys: list[str]) -> str | None:
    for key in keys:
        normalized = _normalize_column(key)
        if normalized in column_map:
            return column_map[normalized]
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-input", default=DEFAULT_BARS_INPUT)
    parser.add_argument("--margin-input", default=None)
    parser.add_argument("--margin-cache", default=DEFAULT_MARGIN_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--availability-lag-days", type=int, default=35)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        margin_input=args.margin_input,
        margin_cache=args.margin_cache,
        availability_lag_days=args.availability_lag_days,
    )
    valid = features.dropna(subset=["margin_debt_rank_120m", "debit_credit_ratio_rank_120m"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
    print(f"availability_lag_days={args.availability_lag_days}")


if __name__ == "__main__":
    main()
