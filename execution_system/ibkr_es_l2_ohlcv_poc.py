#!/usr/bin/env python3
"""
POC: stream Interactive Brokers ES futures L2 depth and print latest 1-minute OHLCV.

Dependencies:
    python3 -m pip install ibapi

You must have TWS or IB Gateway running with API access enabled. Common ports:
    TWS paper:    7497
    TWS live:     7496
    Gateway paper:4002
    Gateway live: 4001

The default bar mode uses IBKR 5-second real-time TRADES bars and aggregates
them locally into 1-minute OHLCV. IBKR's real-time bar API only provides
5-second bars. Use --bar-mode historical-1m to request IBKR's 1-minute
historical bars with keepUpToDate=True instead.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

try:
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.wrapper import EWrapper

    from ibkr_decimal_volume_patch import patch_ibapi_realtime_bar_decimal_volume

    IBAPI_IMPORT_ERROR: ImportError | None = None
except ImportError as exc:  # pragma: no cover - this is for a cleaner CLI error.
    class EClient:  # type: ignore[no-redef]
        pass

    class EWrapper:  # type: ignore[no-redef]
        pass

    Contract = None
    IBAPI_IMPORT_ERROR = exc


DEPTH_REQ_ID = 8101
REALTIME_BARS_REQ_ID = 8102
HISTORICAL_BARS_REQ_ID = 8103

QUARTERLY_MONTHS = (3, 6, 9, 12)


@dataclass
class DepthLevel:
    price: float
    size: Any
    market_maker: str = ""


@dataclass
class MinuteBar:
    start_epoch: int
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: Decimal
    count: int

    def update(
        self,
        high: float,
        low: float,
        close: float,
        volume: Any,
        count: int,
    ) -> None:
        self.high = max(self.high, high)
        self.low = min(self.low, low)
        self.close = close
        self.volume += to_decimal(volume)
        self.count += int(count)

    def print_key(self) -> tuple[Any, ...]:
        return (
            self.start_epoch,
            self.open,
            self.high,
            self.low,
            self.close,
            str(self.volume),
            self.count,
        )


@dataclass(frozen=True)
class BarSnapshot:
    timestamp: Any
    symbol: str
    open: Any
    high: Any
    low: Any
    close: Any
    volume: Any
    count: Any = None

    def print_key(self) -> tuple[Any, ...]:
        return (
            self.timestamp,
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
            self.count,
        )


class MarketDepthBook:
    def __init__(self) -> None:
        self.bids: list[DepthLevel] = []
        self.asks: list[DepthLevel] = []

    def apply(
        self,
        position: int,
        operation: int,
        side: int,
        price: float,
        size: Any,
        market_maker: str = "",
    ) -> None:
        levels = self.asks if side == 0 else self.bids

        if operation == 0:
            index = min(position, len(levels))
            levels.insert(index, DepthLevel(price, size, market_maker))
        elif operation == 1:
            ensure_depth(levels, position)
            levels[position] = DepthLevel(price, size, market_maker)
        elif operation == 2 and 0 <= position < len(levels):
            del levels[position]

    def top_summary(self) -> str:
        return f"bid={format_level(self.bids)} ask={format_level(self.asks)}"


class IbkrPocApp(EWrapper, EClient):
    def __init__(self, args: argparse.Namespace, contract: Any, display_symbol: str) -> None:
        EClient.__init__(self, self)
        self.args = args
        self.contract = contract
        self.display_symbol = display_symbol
        self.depth_book = MarketDepthBook()
        self.started = threading.Event()
        self.done = threading.Event()
        self.started_requests = False
        self.current_minute_bar: MinuteBar | None = None
        self.latest_initial_historical_bar: BarSnapshot | None = None
        self.last_printed_key: tuple[Any, ...] | None = None

    def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IBAPI callback name.
        if self.started_requests:
            return

        self.started_requests = True
        self.started.set()
        print(
            f"Connected to IBKR. nextValidId={orderId}; subscribing to {self.display_symbol}",
            file=sys.stderr,
        )

        self.reqMarketDataType(self.args.market_data_type)
        self.reqMktDepth(
            DEPTH_REQ_ID,
            self.contract,
            self.args.depth_rows,
            self.args.smart_depth,
            [],
        )
        print(
            f"Subscribed to L2 depth rows={self.args.depth_rows} "
            f"smart_depth={self.args.smart_depth}",
            file=sys.stderr,
        )

        if self.args.bar_mode == "historical-1m":
            self.reqHistoricalData(
                HISTORICAL_BARS_REQ_ID,
                self.contract,
                "",
                self.args.duration,
                "1 min",
                self.args.what_to_show,
                self.args.use_rth,
                1,
                True,
                [],
            )
            print(
                "Subscribed to 1-minute historical bars with keepUpToDate=True",
                file=sys.stderr,
            )
        else:
            self.reqRealTimeBars(
                REALTIME_BARS_REQ_ID,
                self.contract,
                5,
                self.args.what_to_show,
                self.args.use_rth,
                [],
            )
            print(
                "Subscribed to 5-second real-time bars; aggregating to 1-minute OHLCV",
                file=sys.stderr,
            )

    def updateMktDepth(  # noqa: N802 - IBAPI callback name.
        self,
        reqId: int,
        position: int,
        operation: int,
        side: int,
        price: float,
        size: Any,
    ) -> None:
        if reqId != DEPTH_REQ_ID:
            return
        self.depth_book.apply(position, operation, side, price, size)
        if self.args.print_depth:
            print(f"L2 {self.display_symbol} {self.depth_book.top_summary()}", file=sys.stderr)

    def updateMktDepthL2(  # noqa: N802 - IBAPI callback name.
        self,
        reqId: int,
        position: int,
        marketMaker: str,
        operation: int,
        side: int,
        price: float,
        size: Any,
        isSmartDepth: bool,
    ) -> None:
        if reqId != DEPTH_REQ_ID:
            return
        self.depth_book.apply(position, operation, side, price, size, marketMaker)
        if self.args.print_depth:
            print(f"L2 {self.display_symbol} {self.depth_book.top_summary()}", file=sys.stderr)

    def realtimeBar(  # noqa: N802 - IBAPI callback name.
        self,
        reqId: int,
        time_: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: Any,
        wap: Any,
        count: int,
    ) -> None:
        if reqId != REALTIME_BARS_REQ_ID:
            return

        minute_start = int(time_) - (int(time_) % 60)
        completed_bar: MinuteBar | None = None

        if self.current_minute_bar is None:
            self.current_minute_bar = MinuteBar(
                minute_start,
                self.display_symbol,
                open_,
                high,
                low,
                close,
                to_decimal(volume),
                int(count),
            )
        elif self.current_minute_bar.start_epoch == minute_start:
            self.current_minute_bar.update(high, low, close, volume, count)
        else:
            completed_bar = self.current_minute_bar
            self.current_minute_bar = MinuteBar(
                minute_start,
                self.display_symbol,
                open_,
                high,
                low,
                close,
                to_decimal(volume),
                int(count),
            )

        if self.args.completed_only:
            if completed_bar:
                self.print_bar(completed_bar, completed=True)
        elif self.current_minute_bar:
            self.print_bar(self.current_minute_bar, completed=False)

    def historicalData(  # noqa: N802 - IBAPI callback name.
        self,
        reqId: int,
        bar: Any,
    ) -> None:
        if reqId != HISTORICAL_BARS_REQ_ID:
            return
        self.latest_initial_historical_bar = snapshot_from_ib_bar(
            bar, self.display_symbol
        )

    def historicalDataEnd(  # noqa: N802 - IBAPI callback name.
        self,
        reqId: int,
        start: str,
        end: str,
    ) -> None:
        if reqId != HISTORICAL_BARS_REQ_ID or not self.latest_initial_historical_bar:
            return
        self.print_bar(self.latest_initial_historical_bar, completed=True)

    def historicalDataUpdate(  # noqa: N802 - IBAPI callback name.
        self,
        reqId: int,
        bar: Any,
    ) -> None:
        if reqId != HISTORICAL_BARS_REQ_ID:
            return
        self.print_bar(snapshot_from_ib_bar(bar, self.display_symbol), completed=False)

    def error(  # noqa: A003,N802 - IBAPI callback name.
        self,
        reqId: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        prefix = "IBKR"
        if reqId >= 0:
            prefix = f"IBKR reqId={reqId}"

        severity = "info" if errorCode in {2103, 2104, 2106, 2107, 2108, 2158} else "error"
        print(f"{prefix} {severity} {errorCode}: {errorString}", file=sys.stderr)

        if errorCode in {200, 354, 10167, 10197}:
            print(
                "Check the ES contract, market data subscriptions, and whether live "
                "data is enabled in TWS/Gateway.",
                file=sys.stderr,
            )

    def connectionClosed(self) -> None:  # noqa: N802 - IBAPI callback name.
        self.done.set()

    def print_bar(self, bar: MinuteBar | BarSnapshot, completed: bool) -> None:
        key = bar.print_key()
        if key == self.last_printed_key:
            return
        self.last_printed_key = key

        suffix = "complete" if completed else "partial"
        print(
            f"{format_timestamp(bar.timestamp if isinstance(bar, BarSnapshot) else bar.start_epoch)} "
            f"{bar.symbol} O={bar.open} H={bar.high} L={bar.low} "
            f"C={bar.close} V={bar.volume} ({suffix})",
            flush=True,
        )

        if self.args.once:
            self.done.set()
            self.disconnect()

    def shutdown(self) -> None:
        if not self.isConnected():
            self.done.set()
            return

        try:
            self.cancelMktDepth(DEPTH_REQ_ID, self.args.smart_depth)
        except Exception:
            pass

        try:
            if self.args.bar_mode == "historical-1m":
                self.cancelHistoricalData(HISTORICAL_BARS_REQ_ID)
            else:
                self.cancelRealTimeBars(REALTIME_BARS_REQ_ID)
        except Exception:
            pass

        self.done.set()
        self.disconnect()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream IBKR ES futures L2 depth and print latest 1-minute OHLCV."
    )
    parser.add_argument(
        "--host",
        default=os.getenv("IB_HOST", "127.0.0.1"),
        help="TWS/Gateway host. Defaults to IB_HOST or 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("IB_PORT", "7497")),
        help="TWS/Gateway API port. Defaults to IB_PORT or 7497.",
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=int(os.getenv("IB_CLIENT_ID", "72")),
        help="Unique API client id. Defaults to IB_CLIENT_ID or 72.",
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
        "--depth-rows",
        type=int,
        default=int(os.getenv("IB_DEPTH_ROWS", "10")),
        help="Number of book rows to request. Defaults to 10.",
    )
    parser.add_argument(
        "--smart-depth",
        action="store_true",
        default=os.getenv("IB_SMART_DEPTH", "").lower() in {"1", "true", "yes"},
        help="Request smart depth aggregation when supported.",
    )
    parser.add_argument(
        "--print-depth",
        action="store_true",
        help="Print top-of-book L2 updates to stderr.",
    )
    parser.add_argument(
        "--market-data-type",
        type=int,
        choices=(1, 2, 3, 4),
        default=int(os.getenv("IB_MARKET_DATA_TYPE", "1")),
        help="1 live, 2 frozen, 3 delayed, 4 delayed-frozen. Defaults to 1.",
    )
    parser.add_argument(
        "--bar-mode",
        choices=("realtime-5s", "historical-1m"),
        default=os.getenv("IB_BAR_MODE", "realtime-5s"),
        help="Use 5-second live bars aggregated to 1m, or IBKR historical 1m keepUpToDate.",
    )
    parser.add_argument(
        "--what-to-show",
        default=os.getenv("IB_WHAT_TO_SHOW", "TRADES"),
        help="IBKR data type for bars. Defaults to TRADES so volume is populated.",
    )
    parser.add_argument(
        "--use-rth",
        type=int,
        choices=(0, 1),
        default=int(os.getenv("IB_USE_RTH", "0")),
        help="1 for regular trading hours only, 0 for all sessions. Defaults to 0.",
    )
    parser.add_argument(
        "--duration",
        default=os.getenv("IB_HIST_DURATION", "1 D"),
        help="Historical duration for --bar-mode historical-1m. Defaults to 1 D.",
    )
    parser.add_argument(
        "--completed-only",
        action="store_true",
        help="Only print completed 1-minute bars in realtime-5s mode.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exit after printing the first OHLCV line.",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=float(os.getenv("IB_CONNECT_TIMEOUT", "15")),
        help="Seconds to wait for nextValidId after connecting. Defaults to 15.",
    )
    parser.add_argument(
        "--max-runtime",
        type=float,
        default=float(os.getenv("IB_MAX_RUNTIME", "0")),
        help="Optional max runtime in seconds. 0 means run until Ctrl-C.",
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


def ensure_depth(levels: list[DepthLevel], position: int) -> None:
    while len(levels) <= position:
        levels.append(DepthLevel(0.0, 0, ""))


def format_level(levels: list[DepthLevel]) -> str:
    if not levels:
        return "-"
    level = levels[0]
    owner = f"@{level.market_maker}" if level.market_maker else ""
    return f"{level.price}x{level.size}{owner}"


def to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def snapshot_from_ib_bar(bar: Any, symbol: str) -> BarSnapshot:
    return BarSnapshot(
        timestamp=bar.date,
        symbol=symbol,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        count=getattr(bar, "barCount", None),
    )


def format_timestamp(value: Any) -> str:
    try:
        epoch = int(value)
    except (TypeError, ValueError):
        return str(value)

    if epoch <= 0:
        return str(value)
    return (
        dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def main() -> int:
    args = parse_args()
    if IBAPI_IMPORT_ERROR is not None:
        print(
            "Missing dependency: python3 -m pip install ibapi",
            file=sys.stderr,
        )
        return 2

    if args.bar_mode == "realtime-5s" and patch_ibapi_realtime_bar_decimal_volume():
        print("Applied IBKR realtime decimal-volume decoder patch.", file=sys.stderr)

    contract = build_es_contract(args)
    app = IbkrPocApp(args, contract, display_symbol(contract))

    print(
        f"Connecting to IBKR TWS/Gateway at {args.host}:{args.port} "
        f"client_id={args.client_id}...",
        file=sys.stderr,
    )
    app.connect(args.host, args.port, args.client_id)

    api_thread = threading.Thread(target=app.run, name="ibkr-api", daemon=True)
    api_thread.start()

    if not app.started.wait(args.connect_timeout):
        print(
            "Timed out waiting for IBKR nextValidId. Check that TWS/Gateway is "
            "running and API access is enabled.",
            file=sys.stderr,
        )
        app.shutdown()
        api_thread.join(timeout=2)
        return 1

    stop_requested = False

    def handle_signal(*_: Any) -> None:
        nonlocal stop_requested
        stop_requested = True
        app.shutdown()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    deadline = time.monotonic() + args.max_runtime if args.max_runtime > 0 else None
    while not app.done.is_set():
        if deadline and time.monotonic() >= deadline:
            app.shutdown()
            break
        time.sleep(0.2)

    app.shutdown()
    api_thread.join(timeout=2)
    return 130 if stop_requested else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001 - this is a CLI POC.
        print(f"fatal: {exc}", file=sys.stderr)
        raise SystemExit(1)
