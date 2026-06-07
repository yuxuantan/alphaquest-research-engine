#!/usr/bin/env python3
"""
Fetch IBKR ES 1-minute historical bars and save them to CSV.

Dependencies:
    python3 -m pip install ibapi

Example:
    python3 ibkr_es_historical_1m_fetch.py --port 4001 --client-id 73 --expiry 202606
    python3 ibkr_es_historical_1m_fetch.py --port 4001 --client-id 73 --expiry 202606 --start 2026-06-01 --end 2026-06-05

The output defaults to:
    data/ibkr/historical/ES_<expiry>_<exchange>_1min_latest.csv
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.wrapper import EWrapper

    IBAPI_IMPORT_ERROR: ImportError | None = None
except ImportError as exc:  # pragma: no cover - this is for a cleaner CLI error.
    class EClient:  # type: ignore[no-redef]
        pass

    class EWrapper:  # type: ignore[no-redef]
        pass

    Contract = None
    IBAPI_IMPORT_ERROR = exc


HISTORICAL_REQ_ID = 9101
QUARTERLY_MONTHS = (3, 6, 9, 12)
INFO_CODES = {2103, 2104, 2106, 2107, 2108, 2158}


@dataclass(frozen=True)
class HistoricalBar:
    timestamp_epoch: int | None
    timestamp_utc: str
    ib_timestamp: str
    symbol: str
    expiry: str
    exchange: str
    open: Any
    high: Any
    low: Any
    close: Any
    volume: Any
    wap: Any
    bar_count: Any

    def sort_key(self) -> tuple[int, str]:
        return (self.timestamp_epoch or 0, self.ib_timestamp)

    def row(self) -> dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc,
            "timestamp_epoch": self.timestamp_epoch or "",
            "ib_timestamp": self.ib_timestamp,
            "symbol": self.symbol,
            "expiry": self.expiry,
            "exchange": self.exchange,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "wap": self.wap,
            "bar_count": self.bar_count,
        }


@dataclass(frozen=True)
class HistoricalRequest:
    index: int
    total: int
    end_datetime: str
    duration: str


class HistoricalFetchApp(EWrapper, EClient):
    def __init__(self, args: argparse.Namespace, contract: Any) -> None:
        EClient.__init__(self, self)
        self.args = args
        self.contract = contract
        self.started = threading.Event()
        self.done = threading.Event()
        self.failed = False
        self.error_messages: list[str] = []
        self.bars: list[HistoricalBar] = []
        self.request_started = False
        self.requests = historical_requests(args)
        self.request_index = -1
        self.current_raw_bar_count = 0
        self.range_start_epoch, self.range_end_epoch = range_epoch_bounds(args)

    def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IBAPI callback name.
        if self.request_started:
            return

        self.request_started = True
        self.started.set()
        print(f"Connected to IBKR. nextValidId={orderId}", file=sys.stderr)
        self.request_next()

    def request_next(self) -> None:
        if self.done.is_set() or self.failed:
            return

        self.request_index += 1
        if self.request_index >= len(self.requests):
            self.done.set()
            return

        request = self.requests[self.request_index]
        self.current_raw_bar_count = 0
        print(
            f"Request {request.index}/{request.total}: {request.duration} of "
            f"1-minute {self.args.what_to_show} bars for {display_symbol(self.contract)} "
            f"ending {request.end_datetime or 'now'}",
            file=sys.stderr,
        )

        self.reqHistoricalData(
            HISTORICAL_REQ_ID,
            self.contract,
            request.end_datetime,
            request.duration,
            "1 min",
            self.args.what_to_show,
            self.args.use_rth,
            2,
            False,
            [],
        )

    def historicalData(  # noqa: N802 - IBAPI callback name.
        self,
        reqId: int,
        bar: Any,
    ) -> None:
        if reqId != HISTORICAL_REQ_ID:
            return
        self.current_raw_bar_count += 1
        historical_bar = historical_bar_from_ib(bar, self.contract)
        if self.bar_in_requested_range(historical_bar):
            self.bars.append(historical_bar)

    def historicalDataEnd(  # noqa: N802 - IBAPI callback name.
        self,
        reqId: int,
        start: str,
        end: str,
    ) -> None:
        if reqId != HISTORICAL_REQ_ID:
            return
        print(
            f"HistoricalDataEnd reqId={reqId} request="
            f"{self.request_index + 1}/{len(self.requests)} start={start} end={end} "
            f"raw_bars={self.current_raw_bar_count} kept_bars={len(self.bars)}",
            file=sys.stderr,
        )
        if self.request_index + 1 >= len(self.requests):
            self.done.set()
            return

        delay = max(0.0, self.args.pace_seconds)
        if delay > 0:
            print(f"Waiting {delay:g}s before next historical request...", file=sys.stderr)
        timer = threading.Timer(delay, self.request_next)
        timer.daemon = True
        timer.start()

    def error(  # noqa: A003,N802 - IBAPI callback name.
        self,
        reqId: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        severity = "info" if errorCode in INFO_CODES else "error"
        prefix = f"IBKR reqId={reqId}" if reqId >= 0 else "IBKR"
        message = f"{prefix} {severity} {errorCode}: {errorString}"
        print(message, file=sys.stderr)

        if reqId == HISTORICAL_REQ_ID and errorCode not in INFO_CODES:
            self.failed = True
            self.error_messages.append(message)
            self.done.set()

    def connectionClosed(self) -> None:  # noqa: N802 - IBAPI callback name.
        self.done.set()

    def shutdown(self) -> None:
        if not self.isConnected():
            self.done.set()
            return

        try:
            self.cancelHistoricalData(HISTORICAL_REQ_ID)
        except Exception:
            pass

        self.disconnect()
        self.done.set()

    def bar_in_requested_range(self, bar: HistoricalBar) -> bool:
        if self.range_start_epoch is None and self.range_end_epoch is None:
            return True
        if bar.timestamp_epoch is None:
            return False
        if self.range_start_epoch is not None and bar.timestamp_epoch < self.range_start_epoch:
            return False
        if self.range_end_epoch is not None and bar.timestamp_epoch > self.range_end_epoch:
            return False
        return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch IBKR ES 1-minute historical bars and save to CSV."
    )
    parser.add_argument(
        "--host",
        default=os.getenv("IB_HOST", "127.0.0.1"),
        help="TWS/Gateway host. Defaults to IB_HOST or 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("IB_PORT", "4001")),
        help="TWS/Gateway API port. Defaults to IB_PORT or 4001.",
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=int(os.getenv("IB_CLIENT_ID", "73")),
        help="Unique API client id. Defaults to IB_CLIENT_ID or 73.",
    )
    parser.add_argument(
        "--symbol",
        default=os.getenv("IB_SYMBOL", "ES"),
        help="Futures root symbol. Defaults to ES.",
    )
    parser.add_argument(
        "--expiry",
        default=os.getenv("IB_ES_EXPIRY"),
        help="Contract month as YYYYMM or YYYYMMDD. Defaults to nearest unexpired quarterly ES month.",
    )
    parser.add_argument(
        "--exchange",
        default=os.getenv("IB_EXCHANGE", "CME"),
        help="IBKR futures exchange. Defaults to CME.",
    )
    parser.add_argument(
        "--currency",
        default=os.getenv("IB_CURRENCY", "USD"),
        help="Contract currency. Defaults to USD.",
    )
    parser.add_argument(
        "--multiplier",
        default=os.getenv("IB_MULTIPLIER", "50"),
        help="Contract multiplier. Defaults to 50 for ES.",
    )
    parser.add_argument(
        "--local-symbol",
        default=os.getenv("IB_LOCAL_SYMBOL"),
        help="Optional IBKR localSymbol, e.g. ESM6. Overrides --expiry matching.",
    )
    parser.add_argument(
        "--duration",
        default=os.getenv("IB_HIST_DURATION", "1 D"),
        help=(
            "Historical duration string for one-shot mode. Defaults to 1 D. "
            "Ignored when --start is set; range mode uses 1 D chunks for 1 min bars."
        ),
    )
    parser.add_argument(
        "--start",
        default=os.getenv("IB_HIST_START"),
        help=(
            "Range start for multi-request mode. Accepts YYYY-MM-DD, YYYYMMDD, "
            "or ISO datetime. Date-only values use --timezone at 00:00:00."
        ),
    )
    parser.add_argument(
        "--end",
        default=os.getenv("IB_HIST_END", ""),
        help=(
            "One-shot mode: raw IBKR endDateTime; empty means now. Range mode: "
            "range end as YYYY-MM-DD, YYYYMMDD, or ISO datetime; empty means now. "
            "Date-only values use --timezone at 23:59:59."
        ),
    )
    parser.add_argument(
        "--timezone",
        default=os.getenv("IB_HIST_TIMEZONE", "Asia/Singapore"),
        help="Timezone for naive --start/--end values. Defaults to Asia/Singapore.",
    )
    parser.add_argument(
        "--pace-seconds",
        type=float,
        default=float(os.getenv("IB_HIST_PACE_SECONDS", "2")),
        help="Delay between range-mode chunk requests. Defaults to 2 seconds.",
    )
    parser.add_argument(
        "--what-to-show",
        default=os.getenv("IB_WHAT_TO_SHOW", "TRADES"),
        help="IBKR historical data type. Defaults to TRADES so volume is populated.",
    )
    parser.add_argument(
        "--use-rth",
        type=int,
        choices=(0, 1),
        default=int(os.getenv("IB_USE_RTH", "0")),
        help="1 for regular trading hours only, 0 for all sessions. Defaults to 0.",
    )
    parser.add_argument(
        "--output",
        default=os.getenv("IB_HIST_OUTPUT"),
        help="CSV output path. Defaults to data/ibkr/historical/<contract>_1min_latest.csv.",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=float(os.getenv("IB_CONNECT_TIMEOUT", "15")),
        help="Seconds to wait for nextValidId after connecting. Defaults to 15.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=float(os.getenv("IB_HIST_REQUEST_TIMEOUT", "60")),
        help="Seconds to wait for historicalDataEnd. Defaults to 60.",
    )
    return parser.parse_args()


def build_es_contract(args: argparse.Namespace) -> Any:
    if Contract is None:
        raise RuntimeError("ibapi is not available")

    contract = Contract()
    contract.symbol = args.symbol
    contract.secType = "FUT"
    contract.exchange = args.exchange
    contract.currency = args.currency

    if args.multiplier:
        contract.multiplier = args.multiplier
    if args.local_symbol:
        contract.localSymbol = args.local_symbol
    else:
        contract.lastTradeDateOrContractMonth = args.expiry or next_quarterly_expiry()

    return contract


def display_symbol(contract: Any) -> str:
    expiry = getattr(contract, "lastTradeDateOrContractMonth", "")
    local_symbol = getattr(contract, "localSymbol", "")
    contract_id = local_symbol or expiry
    return f"{contract.symbol} {contract_id} {contract.exchange}".strip()


def output_path(args: argparse.Namespace, contract: Any) -> Path:
    if args.output:
        return Path(args.output)

    contract_id = (
        getattr(contract, "localSymbol", "")
        or getattr(contract, "lastTradeDateOrContractMonth", "")
        or "front"
    )
    if args.start:
        start_slug = safe_filename_part(args.start)
        end_slug = safe_filename_part(args.end or "now")
        filename = (
            f"{contract.symbol}_{contract_id}_{contract.exchange}_1min_"
            f"{start_slug}_to_{end_slug}.csv"
        )
    else:
        filename = f"{contract.symbol}_{contract_id}_{contract.exchange}_1min_latest.csv"
    return Path("data") / "ibkr" / "historical" / filename


def historical_requests(args: argparse.Namespace) -> list[HistoricalRequest]:
    if not args.start:
        return [HistoricalRequest(1, 1, args.end, args.duration)]

    start_dt, end_dt = parsed_range(args)
    requests: list[HistoricalRequest] = []
    cursor_start = start_dt
    total_seconds = (end_dt - start_dt).total_seconds()
    total = max(1, int((total_seconds + 86_399) // 86_400))

    while cursor_start < end_dt:
        cursor_end = min(cursor_start + dt.timedelta(days=1), end_dt)
        requests.append(
            HistoricalRequest(
                index=len(requests) + 1,
                total=total,
                end_datetime=ib_end_datetime(cursor_end),
                duration="1 D",
            )
        )
        cursor_start = cursor_end

    return [
        HistoricalRequest(index=index + 1, total=len(requests), end_datetime=request.end_datetime, duration=request.duration)
        for index, request in enumerate(requests)
    ]


def range_epoch_bounds(args: argparse.Namespace) -> tuple[int | None, int | None]:
    if not args.start:
        return None, None
    start_dt, end_dt = parsed_range(args)
    return int(start_dt.timestamp()), int(end_dt.timestamp())


def parsed_range(args: argparse.Namespace) -> tuple[dt.datetime, dt.datetime]:
    timezone = load_timezone(args.timezone)
    start_dt = parse_user_datetime(args.start, timezone, is_end=False)
    end_dt = (
        parse_user_datetime(args.end, timezone, is_end=True)
        if args.end
        else dt.datetime.now(dt.timezone.utc)
    )

    if start_dt >= end_dt:
        raise ValueError(f"--start must be before --end: {start_dt} >= {end_dt}")
    return start_dt.astimezone(dt.timezone.utc), end_dt.astimezone(dt.timezone.utc)


def load_timezone(value: str) -> dt.tzinfo:
    if value.upper() in {"UTC", "Z"}:
        return dt.timezone.utc
    if value.startswith(("+", "-")):
        return fixed_offset_timezone(value)
    return ZoneInfo(value)


def fixed_offset_timezone(value: str) -> dt.tzinfo:
    sign = 1 if value.startswith("+") else -1
    raw = value[1:]
    if ":" in raw:
        hours_text, minutes_text = raw.split(":", 1)
    else:
        hours_text, minutes_text = raw, "0"
    offset = dt.timedelta(hours=int(hours_text), minutes=int(minutes_text))
    return dt.timezone(sign * offset)


def parse_user_datetime(value: str, timezone: dt.tzinfo, is_end: bool) -> dt.datetime:
    value = value.strip()
    date_only = parse_date_only(value)
    if date_only is not None:
        time_value = dt.time(23, 59, 59) if is_end else dt.time(0, 0, 0)
        return dt.datetime.combine(date_only, time_value, tzinfo=timezone)

    normalized = value.replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed


def parse_date_only(value: str) -> dt.date | None:
    try:
        if len(value) == 10 and value[4] == "-" and value[7] == "-":
            return dt.date.fromisoformat(value)
        if len(value) == 8 and value.isdigit():
            return dt.datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None
    return None


def ib_end_datetime(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y%m%d %H:%M:%S UTC")


def safe_filename_part(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-")


def historical_bar_from_ib(bar: Any, contract: Any) -> HistoricalBar:
    epoch = parse_epoch(bar.date)
    return HistoricalBar(
        timestamp_epoch=epoch,
        timestamp_utc=format_epoch_utc(epoch) if epoch is not None else "",
        ib_timestamp=str(bar.date),
        symbol=getattr(contract, "symbol", ""),
        expiry=getattr(contract, "localSymbol", "")
        or getattr(contract, "lastTradeDateOrContractMonth", ""),
        exchange=getattr(contract, "exchange", ""),
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        wap=getattr(bar, "wap", ""),
        bar_count=getattr(bar, "barCount", ""),
    )


def parse_epoch(value: Any) -> int | None:
    try:
        epoch = int(str(value))
    except (TypeError, ValueError):
        return None
    return epoch if epoch > 0 else None


def format_epoch_utc(epoch: int) -> str:
    return (
        dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def write_csv(path: Path, bars: list[HistoricalBar]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)

    deduped = {bar.sort_key(): bar for bar in bars}
    ordered = [deduped[key] for key in sorted(deduped)]

    fieldnames = [
        "timestamp_utc",
        "timestamp_epoch",
        "ib_timestamp",
        "symbol",
        "expiry",
        "exchange",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "wap",
        "bar_count",
    ]

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for bar in ordered:
            writer.writerow(bar.row())
    return len(ordered)


def next_quarterly_expiry(now: dt.date | None = None) -> str:
    today = now or dt.datetime.now(dt.timezone.utc).date()
    year = today.year

    for _ in range(8):
        for month in QUARTERLY_MONTHS:
            expiry = third_friday(year, month)
            if expiry >= today:
                return f"{year}{month:02d}"
        year += 1

    raise RuntimeError("Could not determine next quarterly futures expiry")


def third_friday(year: int, month: int) -> dt.date:
    day = dt.date(year, month, 1)
    while day.weekday() != 4:
        day += dt.timedelta(days=1)
    return day + dt.timedelta(days=14)


def main() -> int:
    args = parse_args()
    if IBAPI_IMPORT_ERROR is not None:
        print("Missing dependency: python3 -m pip install ibapi", file=sys.stderr)
        return 2

    contract = build_es_contract(args)
    app = HistoricalFetchApp(args, contract)

    print(
        f"Connecting to IBKR TWS/Gateway at {args.host}:{args.port} "
        f"client_id={args.client_id}...",
        file=sys.stderr,
    )
    app.connect(args.host, args.port, args.client_id)

    api_thread = threading.Thread(target=app.run, name="ibkr-historical-api", daemon=True)
    api_thread.start()

    if not app.started.wait(args.connect_timeout):
        print(
            "Timed out waiting for IBKR nextValidId. Check Gateway API settings and port.",
            file=sys.stderr,
        )
        app.shutdown()
        api_thread.join(timeout=2)
        return 1

    total_timeout = (args.request_timeout + max(0.0, args.pace_seconds)) * len(app.requests) + 5
    if not app.done.wait(total_timeout):
        print(
            f"Timed out waiting for historicalDataEnd after {total_timeout:g}s.",
            file=sys.stderr,
        )
        app.shutdown()
        api_thread.join(timeout=2)
        return 1

    app.shutdown()
    api_thread.join(timeout=2)

    if app.failed:
        return 1
    if not app.bars:
        print("No historical bars returned; not writing output.", file=sys.stderr)
        return 1

    path = output_path(args, contract)
    written = write_csv(path, app.bars)
    print(f"Wrote {written} bars to {path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001 - this is a CLI POC.
        print(f"fatal: {exc}", file=sys.stderr)
        raise SystemExit(1)
