from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = Path("data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet")
DEFAULT_OUTPUT = Path("data/external/spx_0dte_calendar_sessions_20110103_20260609.csv")

WEDNESDAY_LAUNCH = date(2016, 2, 23)
MONDAY_LAUNCH = date(2016, 8, 22)
TUESDAY_LAUNCH = date(2022, 4, 18)
THURSDAY_LAUNCH = date(2022, 5, 11)
FULL_WEEK_LAUNCH = THURSDAY_LAUNCH


def build_spx_0dte_rows(input_path: str | Path = DEFAULT_INPUT) -> list[dict]:
    sessions = _session_dates(input_path)
    monthly_opex_dates = _third_fridays(sessions)
    rows = []
    for session_date in sessions:
        weekday = session_date.weekday()
        is_standard_monthly = session_date in monthly_opex_dates
        is_quarterly_month = is_standard_monthly and session_date.month in {3, 6, 9, 12}
        is_mwf = _is_mwf_0dte(session_date)
        is_new_tue_thu = _is_new_tue_thu_0dte(session_date)
        is_spx_0dte = is_mwf or is_new_tue_thu
        rows.append(
            {
                "signal_date": session_date.isoformat(),
                "weekday": weekday,
                "weekday_name": session_date.strftime("%A"),
                "is_spx_0dte": _bool_text(is_spx_0dte),
                "is_full_week_0dte": _bool_text(is_spx_0dte and session_date >= FULL_WEEK_LAUNCH),
                "is_new_tue_thu_0dte": _bool_text(is_new_tue_thu),
                "is_mwf_0dte": _bool_text(is_mwf),
                "is_standard_monthly": _bool_text(is_standard_monthly),
                "is_quarterly_month": _bool_text(is_quarterly_month),
                "calendar_rule": _calendar_rule(session_date, is_spx_0dte),
            }
        )
    return rows


def write_calendar(input_path: str | Path = DEFAULT_INPUT, output_path: str | Path = DEFAULT_OUTPUT) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(build_spx_0dte_rows(input_path)).to_csv(output, index=False)
    return output


def _session_dates(input_path: str | Path) -> list[date]:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"ES RTH cache does not exist: {path}")
    df = pd.read_parquet(path)
    if "is_rth" in df.columns:
        df = df[df["is_rth"].fillna(False).astype(bool)]
    if "session_date" in df.columns:
        session_values = pd.to_datetime(df["session_date"]).dt.date
    else:
        session_values = pd.to_datetime(df["timestamp"]).dt.tz_localize(None).dt.date
    sessions = session_values.dropna().drop_duplicates().sort_values()
    return list(sessions)


def _is_mwf_0dte(session_date: date) -> bool:
    weekday = session_date.weekday()
    if weekday == 4:
        return True
    if weekday == 2:
        return session_date >= WEDNESDAY_LAUNCH
    if weekday == 0:
        return session_date >= MONDAY_LAUNCH
    return False


def _is_new_tue_thu_0dte(session_date: date) -> bool:
    weekday = session_date.weekday()
    if weekday == 1:
        return session_date >= TUESDAY_LAUNCH
    if weekday == 3:
        return session_date >= THURSDAY_LAUNCH
    return False


def _calendar_rule(session_date: date, is_spx_0dte: bool) -> str:
    if not is_spx_0dte:
        return "no_spx_0dte_listing_rule"
    weekday = session_date.weekday()
    if weekday == 4:
        return "friday_weekly_or_standard_spx_expiration"
    if weekday == 2:
        return "wednesday_weekly_launch_2016_02_23"
    if weekday == 0:
        return "monday_weekly_launch_2016_08_22"
    if weekday == 1:
        return "tuesday_weekly_launch_2022_04_18"
    if weekday == 3:
        return "thursday_weekly_launch_2022_05_11"
    return "unsupported_weekday"


def _third_fridays(sessions: list[date]) -> set[date]:
    session_set = set(sessions)
    if not sessions:
        return set()
    start = min(sessions).replace(day=1)
    end = max(sessions).replace(day=1)
    months = pd.date_range(start, end, freq="MS")
    out: set[date] = set()
    for month_start in months:
        fridays = pd.date_range(month_start, month_start + pd.offsets.MonthEnd(0), freq="W-FRI")
        if len(fridays) < 3:
            continue
        third_friday = fridays[2].date()
        if third_friday in session_set:
            out.add(third_friday)
    return out


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local SPX 0DTE session calendar from ES RTH sessions.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Local ES RTH parquet cache.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output CSV path.")
    args = parser.parse_args()
    output = write_calendar(args.input, args.output)
    print(output)


if __name__ == "__main__":
    main()
