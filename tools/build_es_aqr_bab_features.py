from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import re
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pandas as pd


DEFAULT_ES_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_AQR_INPUT = "data/external/aqr_bab_equity_factors_daily.xlsx"
DEFAULT_OUTPUT = "data/external/es_aqr_bab_features_20110103_20260609.csv"
AQR_BAB_URL = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Betting-Against-Beta-Equity-Factors-Daily.xlsx"
NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def build_features(
    es_input_path: str | Path,
    aqr_workbook_path: str | Path,
    output_path: str | Path,
    *,
    publication_lag_calendar_days: int = 45,
) -> pd.DataFrame:
    if publication_lag_calendar_days < 0:
        raise ValueError("publication_lag_calendar_days must be non-negative.")

    sessions = _es_sessions(es_input_path)
    bab = _load_aqr_bab_usa(aqr_workbook_path)
    bab = _add_bab_state_features(bab)

    sessions["availability_cutoff"] = sessions["session_date_ts"] - pd.to_timedelta(
        publication_lag_calendar_days,
        unit="D",
    )
    merged = pd.merge_asof(
        sessions.sort_values("availability_cutoff", kind="mergesort"),
        bab.sort_values("observation_date_ts", kind="mergesort"),
        left_on="availability_cutoff",
        right_on="observation_date_ts",
        direction="backward",
    ).sort_values("session_date_ts", kind="mergesort")

    merged["publication_lag_calendar_days"] = publication_lag_calendar_days
    merged["observation_age_days"] = (
        merged["session_date_ts"] - merged["observation_date_ts"]
    ).dt.days
    merged["availability_cutoff"] = merged["availability_cutoff"].dt.date.astype(str)
    merged["observation_date"] = merged["observation_date_ts"].dt.date.astype(str)

    columns = [
        "session_date",
        "observation_date",
        "availability_cutoff",
        "publication_lag_calendar_days",
        "observation_age_days",
        "bab_usa_return_1d",
        "bab_usa_abs_return_1d",
        "bab_usa_return_21d",
        "bab_usa_return_63d",
        "bab_usa_return_126d",
        "bab_usa_mean_21d",
        "bab_usa_mean_63d",
        "bab_usa_z_63d",
        "bab_usa_z_126d",
        "bab_usa_return_rank_252",
        "bab_usa_abs_return_rank_252",
        "bab_usa_sum21_rank_252",
        "bab_usa_sum63_rank_252",
        "bab_usa_sum126_rank_252",
        "bab_usa_z63_rank_252",
        "bab_usa_z126_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].reset_index(drop=True)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _es_sessions(path: str | Path) -> pd.DataFrame:
    bars = pd.read_parquet(path, columns=["timestamp"])
    timestamps = pd.to_datetime(bars["timestamp"])
    sessions = (
        pd.DataFrame({"session_date": timestamps.dt.date.astype(str)})
        .drop_duplicates()
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])
    return sessions


def _load_aqr_bab_usa(path: str | Path) -> pd.DataFrame:
    rows = _read_xlsx_sheet(Path(path), "BAB Factors")
    header_index = next(
        (idx for idx, row in enumerate(rows) if row.get("A") == "DATE" and "USA" in row.values()),
        None,
    )
    if header_index is None:
        raise ValueError("Could not locate DATE/USA header row in AQR BAB workbook.")

    header = rows[header_index]
    usa_column = next((col for col, value in header.items() if value == "USA"), None)
    if usa_column is None:
        raise ValueError("Could not locate USA column in AQR BAB workbook.")

    records: list[dict] = []
    for row in rows[header_index + 1 :]:
        raw_date = row.get("A")
        raw_value = row.get(usa_column)
        if not raw_date or raw_value in {None, ""}:
            continue
        try:
            observation_date = pd.to_datetime(str(raw_date), format="%m/%d/%Y")
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        records.append(
            {
                "observation_date": observation_date.date().isoformat(),
                "observation_date_ts": observation_date.normalize(),
                "bab_usa_return_1d": value,
            }
        )

    if not records:
        raise ValueError("No USA BAB observations found in AQR workbook.")
    return pd.DataFrame(records).sort_values("observation_date_ts", kind="mergesort").reset_index(drop=True)


def _add_bab_state_features(bab: pd.DataFrame) -> pd.DataFrame:
    out = bab.copy()
    r = out["bab_usa_return_1d"].astype(float)
    out["bab_usa_abs_return_1d"] = r.abs()
    for window in (21, 63, 126):
        out[f"bab_usa_return_{window}d"] = r.rolling(window, min_periods=window).sum()
        out[f"bab_usa_mean_{window}d"] = r.rolling(window, min_periods=window).mean()
    out["bab_usa_z_63d"] = _rolling_zscore(r, 63)
    out["bab_usa_z_126d"] = _rolling_zscore(r, 126)
    out["bab_usa_return_rank_252"] = _rolling_last_percentile(out["bab_usa_return_1d"], 252, min_periods=126)
    out["bab_usa_abs_return_rank_252"] = _rolling_last_percentile(out["bab_usa_abs_return_1d"], 252, min_periods=126)
    out["bab_usa_sum21_rank_252"] = _rolling_last_percentile(out["bab_usa_return_21d"], 252, min_periods=126)
    out["bab_usa_sum63_rank_252"] = _rolling_last_percentile(out["bab_usa_return_63d"], 252, min_periods=126)
    out["bab_usa_sum126_rank_252"] = _rolling_last_percentile(out["bab_usa_return_126d"], 252, min_periods=126)
    out["bab_usa_z63_rank_252"] = _rolling_last_percentile(out["bab_usa_z_63d"], 252, min_periods=126)
    out["bab_usa_z126_rank_252"] = _rolling_last_percentile(out["bab_usa_z_126d"], 252, min_periods=126)
    return out


def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std(ddof=0)
    return (series - mean) / std


def _rolling_last_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def percentile(values) -> float:
        clean = pd.Series(values).dropna()
        if clean.empty:
            return float("nan")
        return float(clean.rank(pct=True, method="average").iloc[-1])

    return series.rolling(window, min_periods=min_periods).apply(percentile, raw=False)


def _read_xlsx_sheet(path: Path, sheet_name: str) -> list[dict[str, str]]:
    with ZipFile(path) as zf:
        shared_strings = _shared_strings(zf)
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        target = None
        for sheet in workbook.find("a:sheets", NS):
            if sheet.attrib["name"] == sheet_name:
                rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
                target = rid_to_target[rid]
                break
        if target is None:
            raise ValueError(f"Sheet not found in workbook: {sheet_name}")
        sheet_path = f"xl/{target}" if not target.startswith("/") else target[1:]
        root = ET.fromstring(zf.read(sheet_path))

    rows: list[dict[str, str]] = []
    for row in root.findall("a:sheetData/a:row", NS):
        values: dict[str, str] = {}
        for cell in row.findall("a:c", NS):
            ref = cell.attrib.get("r", "")
            column = _cell_column(ref)
            if not column:
                continue
            values[column] = _cell_value(cell, shared_strings)
        rows.append(values)
    return rows


def _shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    out = []
    for item in root.findall("a:si", NS):
        out.append("".join(text.text or "" for text in item.findall(".//a:t", NS)))
    return out


def _cell_column(ref: str) -> str:
    match = re.match(r"([A-Z]+)", ref)
    return match.group(1) if match else ""


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value = cell.find("a:v", NS)
    if value is None:
        inline = cell.find("a:is", NS)
        if inline is None:
            return ""
        return "".join(text.text or "" for text in inline.findall(".//a:t", NS))
    raw = value.text or ""
    if cell.attrib.get("t") == "s":
        return shared_strings[int(raw)]
    return raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--es-input", default=DEFAULT_ES_INPUT)
    parser.add_argument("--aqr-workbook", default=DEFAULT_AQR_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--publication-lag-calendar-days", type=int, default=45)
    args = parser.parse_args()
    features = build_features(
        args.es_input,
        args.aqr_workbook,
        args.output,
        publication_lag_calendar_days=args.publication_lag_calendar_days,
    )
    valid = features.dropna(subset=["bab_usa_return_rank_252", "bab_usa_sum63_rank_252", "bab_usa_z63_rank_252"])
    print(f"source={AQR_BAB_URL}")
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
    print(f"observation_range={features['observation_date'].min()}..{features['observation_date'].max()}")
    print(f"publication_lag_calendar_days={args.publication_lag_calendar_days}")


if __name__ == "__main__":
    main()
