from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_BARS_INPUT = Path("data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet")
DEFAULT_AUCTIONS_CACHE = Path("data/external/treasury_auctions_query_20110101_20260609.csv")
DEFAULT_OUTPUT = Path("data/external/es_treasury_coupon_auction_sessions_20110103_20260609.csv")
AUCTIONS_ENDPOINT = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"
AUCTION_FIELDS = [
    "record_date",
    "security_type",
    "security_term",
    "auction_date",
    "announcemt_date",
    "offering_amt",
    "total_accepted",
    "closing_time_comp",
]


def build_calendar(
    bars_input: str | Path = DEFAULT_BARS_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    auctions_input: str | Path | None = None,
    auctions_cache: str | Path = DEFAULT_AUCTIONS_CACHE,
    start_date: str = "2011-01-03",
    end_date: str = "2026-06-09",
) -> pd.DataFrame:
    sessions = _session_dates(bars_input)
    sessions = [session for session in sessions if start_date <= session.isoformat() <= end_date]
    session_set = set(sessions)
    auctions = _load_auctions(
        auctions_input=auctions_input,
        auctions_cache=auctions_cache,
        start_date=start_date,
        end_date=end_date,
    )
    coupon = _coupon_auctions_known_before_session(auctions)
    coupon = coupon[coupon["auction_date"].isin(session_set)].copy()
    rows = []
    for auction_date, group in coupon.groupby("auction_date", sort=True):
        terms = sorted(group["security_term"].dropna().astype(str).unique())
        security_types = sorted(group["security_type"].dropna().astype(str).unique())
        announcement_dates = sorted(group["announcemt_date"].dropna().astype(str).unique())
        closing_times = sorted(group["closing_time_comp"].dropna().astype(str).unique())
        note_count = int((group["security_type"] == "Note").sum())
        bond_count = int((group["security_type"] == "Bond").sum())
        rows.append(
            {
                "signal_date": auction_date.isoformat(),
                "coupon_count": int(note_count + bond_count),
                "note_count": note_count,
                "bond_count": bond_count,
                "terms": ";".join(terms),
                "security_types": ";".join(security_types),
                "announcement_dates": ";".join(announcement_dates),
                "closing_times": ";".join(closing_times),
                "source_row_count": int(len(group)),
            }
        )
    out = pd.DataFrame(rows).sort_values("signal_date", kind="mergesort").reset_index(drop=True)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return out


def _session_dates(input_path: str | Path) -> list[date]:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"ES RTH cache does not exist: {path}")
    df = pd.read_parquet(path, columns=None)
    if "is_rth" in df.columns:
        df = df[df["is_rth"].fillna(False).astype(bool)]
    if "session_date" in df.columns:
        session_values = pd.to_datetime(df["session_date"]).dt.date
    elif "timestamp" in df.columns:
        session_values = pd.to_datetime(df["timestamp"]).dt.tz_localize(None).dt.date
    else:
        raise ValueError("ES bar cache must include timestamp or session_date.")
    sessions = session_values.dropna().drop_duplicates().sort_values()
    return list(sessions)


def _load_auctions(
    *,
    auctions_input: str | Path | None,
    auctions_cache: str | Path,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    if auctions_input is not None:
        raw = pd.read_csv(auctions_input)
    else:
        cache_path = Path(auctions_cache)
        if cache_path.exists():
            raw = pd.read_csv(cache_path)
        else:
            raw = _download_auctions(start_date=start_date, end_date=end_date)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            raw.to_csv(cache_path, index=False)
    missing = set(AUCTION_FIELDS) - set(raw.columns)
    if missing:
        raise ValueError(f"Treasury auctions input missing column(s): {sorted(missing)}")
    out = raw.copy()
    out["security_type"] = out["security_type"].astype(str).str.strip()
    out["security_term"] = out["security_term"].astype(str).str.strip()
    out["auction_date"] = pd.to_datetime(out["auction_date"], errors="coerce").dt.date
    out["announcemt_date"] = pd.to_datetime(out["announcemt_date"], errors="coerce").dt.date
    out["closing_time_comp"] = out["closing_time_comp"].fillna("").astype(str).str.strip()
    return out.dropna(subset=["auction_date", "announcemt_date"]).reset_index(drop=True)


def _download_auctions(start_date: str, end_date: str, page_size: int = 1000) -> pd.DataFrame:
    frames = []
    page = 1
    while True:
        query = urlencode(
            {
                "fields": ",".join(AUCTION_FIELDS),
                "filter": f"auction_date:gte:{start_date},auction_date:lte:{end_date}",
                "sort": "auction_date,security_type,security_term",
                "page[size]": page_size,
                "page[number]": page,
            }
        )
        frame = _read_fiscaldata_json(f"{AUCTIONS_ENDPOINT}?{query}")
        if frame.empty:
            break
        frames.append(frame)
        if len(frame) < page_size:
            break
        page += 1
    if not frames:
        raise RuntimeError("No Treasury auction rows downloaded from FiscalData.")
    return pd.concat(frames, ignore_index=True)


def _read_fiscaldata_json(url: str, attempts: int = 4, sleep_seconds: float = 1.5) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read())
            return pd.DataFrame(payload.get("data", []))
        except Exception as exc:  # pragma: no cover - network retry path.
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(sleep_seconds * attempt)
    raise RuntimeError(f"Failed to download free FiscalData JSON after {attempts} attempts: {url}") from last_error


def _coupon_auctions_known_before_session(auctions: pd.DataFrame) -> pd.DataFrame:
    out = auctions[auctions["security_type"].isin({"Note", "Bond"})].copy()
    return out[out["announcemt_date"] < out["auction_date"]].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a no-lookahead nominal Treasury Note/Bond auction calendar for ES research."
    )
    parser.add_argument("--bars-input", default=str(DEFAULT_BARS_INPUT), help="Local ES RTH parquet cache.")
    parser.add_argument("--auctions-input", default=None, help="Optional local Treasury auctions CSV.")
    parser.add_argument("--auctions-cache", default=str(DEFAULT_AUCTIONS_CACHE), help="Free FiscalData cache path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output calendar CSV.")
    parser.add_argument("--start-date", default="2011-01-03")
    parser.add_argument("--end-date", default="2026-06-09")
    args = parser.parse_args()
    out = build_calendar(
        args.bars_input,
        args.output,
        auctions_input=args.auctions_input,
        auctions_cache=args.auctions_cache,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    years = (pd.Timestamp(out["signal_date"].max()) - pd.Timestamp(out["signal_date"].min())).days / 365.25
    print(f"wrote {args.output}")
    print(f"rows={len(out)} date_range={out['signal_date'].min()}..{out['signal_date'].max()}")
    print(f"events_per_year={len(out) / years:.1f}" if years > 0 else "events_per_year=nan")
    print(f"note_days={int((out['note_count'] > 0).sum())} bond_days={int((out['bond_count'] > 0).sum())}")


if __name__ == "__main__":
    main()
