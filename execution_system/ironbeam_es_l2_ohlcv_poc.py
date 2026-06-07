#!/usr/bin/env python3
"""
POC: stream IronBeam ES futures L2 depth and print the latest 1-minute OHLCV bar.

Dependencies:
    python3 -m pip install websocket-client

Credentials are read from environment variables by default:
    IRONBEAM_USERNAME=...
    IRONBEAM_API_KEY=...
    IRONBEAM_PASSWORD=...      # optional, if your IronBeam API account requires it
    IRONBEAM_ENV=live          # live or demo
    IRONBEAM_SYMBOL=XCME:ES.M26

If IRONBEAM_SYMBOL is omitted, the script queries IronBeam's futures symbol search for
XCME/ES and picks the nearest unexpired quarterly ES contract.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

try:
    import websocket
except ImportError:  # pragma: no cover - this is for a cleaner CLI error.
    websocket = None


BASE_URLS = {
    "demo": "https://demo.ironbeamapi.com/v2",
    "live": "https://live.ironbeamapi.com/v2",
}
WS_URLS = {
    "demo": "wss://demo.ironbeamapi.com/v2",
    "live": "wss://live.ironbeamapi.com/v2",
}

MONTH_TO_NUM = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


@dataclass(frozen=True)
class OhlcvBar:
    symbol: str
    timestamp: Any
    open: Any
    high: Any
    low: Any
    close: Any
    volume: Any
    trade_count: Any = None
    source: str = ""

    def print_key(self) -> tuple[Any, Any, Any, Any, Any, Any]:
        return (self.timestamp, self.open, self.high, self.low, self.close, self.volume)


class IronbeamClient:
    def __init__(
        self,
        env: str,
        username: str,
        api_key: str | None,
        password: str | None,
        api_key_field: str,
        api_key_as_password: bool,
        timeout: float,
    ) -> None:
        self.env = env
        self.base_url = BASE_URLS[env]
        self.ws_url = WS_URLS[env]
        self.username = username
        self.api_key = api_key
        self.password = password
        self.api_key_field = api_key_field
        self.api_key_as_password = api_key_as_password
        self.timeout = timeout
        self.token: str | None = None

    def authenticate(self) -> str:
        payload: dict[str, Any] = {"username": self.username}

        if self.password:
            payload["password"] = self.password
        if self.api_key:
            if self.api_key_as_password and not self.password:
                payload["password"] = self.api_key
            else:
                payload[self.api_key_field] = self.api_key

        if "password" not in payload and self.api_key_field not in payload:
            raise SystemExit(
                "Missing credentials. Set IRONBEAM_API_KEY or IRONBEAM_PASSWORD."
            )

        data = self._request_json("POST", "/auth", payload=payload, token=None)
        token = data.get("token")
        if not token:
            raise RuntimeError(f"Auth response did not contain token: {scrub(data)}")

        self.token = str(token)
        return self.token

    def create_stream(self) -> str:
        data = self._request_json("GET", "/stream/create")
        stream_id = data.get("streamId")
        if not stream_id:
            raise RuntimeError(f"Stream response did not contain streamId: {data}")
        return str(stream_id)

    def subscribe_depths(self, stream_id: str, symbol: str) -> None:
        self._request_json(
            "GET",
            f"/market/depths/subscribe/{quote_path(stream_id)}",
            params={"symbols": symbol},
        )

    def subscribe_time_bars(
        self, stream_id: str, symbol: str, period: int, load_size: int
    ) -> dict[str, Any]:
        payload = {
            "symbol": symbol,
            "period": period,
            "barType": "MINUTE",
            "loadSize": load_size,
        }
        return self._request_json(
            "POST",
            f"/indicator/{quote_path(stream_id)}/timeBars/subscribe",
            payload=payload,
        )

    def search_futures(self, exchange: str, market_group: str) -> list[dict[str, Any]]:
        data = self._request_json(
            "GET",
            f"/info/symbol/search/futures/{quote_path(exchange)}/{quote_path(market_group)}",
        )
        symbols = data.get("symbols", [])
        return symbols if isinstance(symbols, list) else []

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        token: str | None | object = ...,
    ) -> dict[str, Any]:
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            path = f"{path}?{query}"

        body = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "ironbeam-es-l2-ohlcv-poc/0.1",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        bearer = self.token if token is ... else token
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"

        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"{method} {path} failed with HTTP {exc.code}: {raw}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{method} {path} failed: {exc.reason}") from exc

        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{method} {path} returned non-JSON: {raw[:500]}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream IronBeam L2 depth for ES and print latest 1-minute OHLCV bars."
    )
    parser.add_argument(
        "--env",
        choices=sorted(BASE_URLS),
        default=os.getenv("IRONBEAM_ENV", "live").lower(),
        help="IronBeam environment. Defaults to IRONBEAM_ENV or live.",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("IRONBEAM_USERNAME"),
        help="IronBeam username/account id. Defaults to IRONBEAM_USERNAME.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("IRONBEAM_API_KEY"),
        help="IronBeam API key. Defaults to IRONBEAM_API_KEY.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("IRONBEAM_PASSWORD"),
        help="Optional IronBeam password. Defaults to IRONBEAM_PASSWORD.",
    )
    parser.add_argument(
        "--api-key-field",
        choices=("apikey", "apiKey"),
        default=os.getenv("IRONBEAM_API_KEY_FIELD", "apikey"),
        help="Auth JSON field for the API key. Defaults to apikey.",
    )
    parser.add_argument(
        "--api-key-as-password",
        action="store_true",
        default=os.getenv("IRONBEAM_API_KEY_AS_PASSWORD", "").lower()
        in {"1", "true", "yes"},
        help="Put the API key in the password field for non-enterprise auth.",
    )
    parser.add_argument(
        "--symbol",
        default=os.getenv("IRONBEAM_SYMBOL"),
        help=(
            "Exact IronBeam symbol, e.g. XCME:ES.M26. Defaults to IRONBEAM_SYMBOL; "
            "if omitted, the script auto-selects a nearby XCME/ES quarterly future."
        ),
    )
    parser.add_argument(
        "--exchange",
        default=os.getenv("IRONBEAM_EXCHANGE", "XCME"),
        help="Exchange/source for auto symbol lookup. Defaults to XCME.",
    )
    parser.add_argument(
        "--market-group",
        default=os.getenv("IRONBEAM_MARKET_GROUP", "ES"),
        help="Market group for auto symbol lookup. Defaults to ES.",
    )
    parser.add_argument(
        "--period",
        type=int,
        default=int(os.getenv("IRONBEAM_BAR_PERIOD", "1")),
        help="Minute bar period. Defaults to 1.",
    )
    parser.add_argument(
        "--load-size",
        type=int,
        default=int(os.getenv("IRONBEAM_BAR_LOAD_SIZE", "2")),
        help="Initial number of time bars to request. Defaults to 2.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exit after printing the first OHLCV bar received.",
    )
    parser.add_argument(
        "--print-depth",
        action="store_true",
        help="Also print top-of-book depth updates to stderr.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print raw non-bar websocket messages to stderr.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("IRONBEAM_HTTP_TIMEOUT", "20")),
        help="HTTP timeout in seconds. Defaults to 20.",
    )
    return parser.parse_args()


def quote_path(value: str) -> str:
    return urllib.parse.quote(str(value), safe="")


def scrub(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            key: "***" if key.lower() in {"token", "password", "apikey"} else scrub(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [scrub(value) for value in data]
    return data


def choose_front_es_symbol(symbols: list[dict[str, Any]]) -> str:
    candidates: list[tuple[dt.date, str]] = []
    today = dt.datetime.now(dt.timezone.utc).date()

    for item in symbols:
        symbol = item.get("symbol")
        year = item.get("maturityYear")
        month_name = str(item.get("maturityMonth", "")).upper()
        month = MONTH_TO_NUM.get(month_name)
        if not symbol or not year or not month:
            continue

        expiry = third_friday(int(year), int(month))
        if expiry >= today:
            candidates.append((expiry, str(symbol)))

    if not candidates:
        available = ", ".join(str(item.get("symbol")) for item in symbols[:10])
        raise RuntimeError(f"Could not auto-select an ES future. Symbols returned: {available}")

    candidates.sort(key=lambda value: value[0])
    return candidates[0][1]


def third_friday(year: int, month: int) -> dt.date:
    day = dt.date(year, month, 1)
    while day.weekday() != 4:
        day += dt.timedelta(days=1)
    return day + dt.timedelta(days=14)


def parse_ws_json(raw: str | bytes) -> dict[str, Any] | None:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def extract_bars(
    data: dict[str, Any],
    symbol: str,
    indicator_value_names: dict[str, list[str]],
) -> list[OhlcvBar]:
    bars: list[OhlcvBar] = []

    for key in ("tc", "ti", "tb", "vb"):
        values = data.get(key)
        if isinstance(values, list):
            for value in values:
                if isinstance(value, dict):
                    bar = bar_from_mapping(value, symbol, source=key)
                    if bar:
                        bars.append(bar)

    indicators = data.get("i")
    if isinstance(indicators, list):
        for indicator in indicators:
            if not isinstance(indicator, dict):
                continue
            indicator_id = str(indicator.get("n") or indicator.get("i") or "")
            value_names = indicator_value_names.get(indicator_id)
            rows = indicator.get("v")
            if not value_names or not isinstance(rows, list):
                continue
            for row in rows:
                mapped = map_indicator_row(row, value_names)
                if mapped:
                    bar = bar_from_mapping(mapped, symbol, source=f"indicator:{indicator_id}")
                    if bar:
                        bars.append(bar)

    return bars


def map_indicator_row(row: Any, value_names: list[str]) -> dict[str, Any] | None:
    if isinstance(row, dict):
        return row
    if isinstance(row, list):
        return {name: row[index] for index, name in enumerate(value_names) if index < len(row)}
    return None


def bar_from_mapping(data: dict[str, Any], default_symbol: str, source: str) -> OhlcvBar | None:
    timestamp = first_present(data, "t", "date", "time", "timestamp")
    open_price = first_present(data, "o", "open")
    high_price = first_present(data, "h", "high")
    low_price = first_present(data, "l", "low")
    close_price = first_present(data, "c", "close")
    volume = first_present(data, "v", "volume")

    if None in (timestamp, open_price, high_price, low_price, close_price, volume):
        return None

    return OhlcvBar(
        symbol=str(first_present(data, "s", "symbol") or default_symbol),
        timestamp=timestamp,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        volume=volume,
        trade_count=first_present(data, "tc", "tradeCount"),
        source=source,
    )


def first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def normalized_time(value: Any) -> float:
    if isinstance(value, str):
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return 0.0

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0

    if numeric > 10_000_000_000_000:
        return numeric / 1_000_000.0
    if numeric > 10_000_000_000:
        return numeric / 1_000.0
    return numeric


def format_time(value: Any) -> str:
    epoch = normalized_time(value)
    if epoch > 0:
        return (
            dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    return str(value)


def format_bar(bar: OhlcvBar) -> str:
    return (
        f"{format_time(bar.timestamp)} {bar.symbol} "
        f"O={bar.open} H={bar.high} L={bar.low} C={bar.close} V={bar.volume}"
    )


def print_depth_summary(data: dict[str, Any], symbol: str) -> None:
    depths = data.get("d") or data.get("Depths")
    if not isinstance(depths, list):
        return
    for depth in depths:
        if not isinstance(depth, dict):
            continue
        if str(depth.get("s") or depth.get("symbol") or symbol) != symbol:
            continue
        bids = depth.get("b") or []
        asks = depth.get("a") or []
        best_bid = first_level(bids)
        best_ask = first_level(asks)
        if best_bid or best_ask:
            print(f"L2 {symbol} bid={best_bid} ask={best_ask}", file=sys.stderr)


def first_level(levels: Any) -> str:
    if not isinstance(levels, list) or not levels:
        return "-"
    level = levels[0]
    if not isinstance(level, dict):
        return str(level)
    price = first_present(level, "p", "price")
    size = first_present(level, "sz", "size", "qty", "quantity")
    return f"{price}x{size}"


def main() -> int:
    args = parse_args()
    if websocket is None:
        print("Missing dependency: python3 -m pip install websocket-client", file=sys.stderr)
        return 2
    if not args.username:
        print("Missing --username or IRONBEAM_USERNAME.", file=sys.stderr)
        return 2

    client = IronbeamClient(
        env=args.env,
        username=args.username,
        api_key=args.api_key,
        password=args.password,
        api_key_field=args.api_key_field,
        api_key_as_password=args.api_key_as_password,
        timeout=args.timeout,
    )

    print(f"Authenticating to IronBeam {args.env}...", file=sys.stderr)
    token = client.authenticate()

    symbol = args.symbol
    if not symbol:
        print(
            f"IRONBEAM_SYMBOL not set; searching {args.exchange}/{args.market_group} futures...",
            file=sys.stderr,
        )
        symbol = choose_front_es_symbol(client.search_futures(args.exchange, args.market_group))
        print(f"Auto-selected symbol {symbol}", file=sys.stderr)

    stream_id = client.create_stream()
    print(f"Created stream {stream_id}", file=sys.stderr)

    indicator_value_names: dict[str, list[str]] = {}
    stop_after_first_bar = {"value": False}
    last_printed: dict[str, tuple[Any, Any, Any, Any, Any, Any]] = {}

    def on_open(ws: websocket.WebSocketApp) -> None:
        try:
            client.subscribe_depths(stream_id, symbol)
            print(f"Subscribed to L2 depth for {symbol}", file=sys.stderr)

            indicator = client.subscribe_time_bars(
                stream_id=stream_id,
                symbol=symbol,
                period=args.period,
                load_size=args.load_size,
            )
            indicator_id = indicator.get("indicatorId")
            value_names = indicator.get("valueNames")
            if indicator_id and isinstance(value_names, list):
                indicator_value_names[str(indicator_id)] = [str(value) for value in value_names]
                print(
                    f"Subscribed to {args.period}-minute time bars "
                    f"({indicator_id})",
                    file=sys.stderr,
                )
            else:
                print(
                    f"Subscribed to {args.period}-minute time bars: {indicator}",
                    file=sys.stderr,
                )
        except Exception as exc:  # noqa: BLE001 - keep the POC failure visible.
            print(f"Subscription failed: {exc}", file=sys.stderr)
            ws.close()

    def on_message(ws: websocket.WebSocketApp, raw: str | bytes) -> None:
        data = parse_ws_json(raw)
        if data is None:
            if args.debug:
                print(f"Non-JSON websocket message: {raw!r}", file=sys.stderr)
            return

        if args.print_depth:
            print_depth_summary(data, symbol)

        bars = extract_bars(data, symbol, indicator_value_names)
        if bars:
            latest = max(bars, key=lambda bar: normalized_time(bar.timestamp))
            previous = last_printed.get(latest.symbol)
            if latest.print_key() != previous:
                print(format_bar(latest), flush=True)
                last_printed[latest.symbol] = latest.print_key()
                if args.once:
                    stop_after_first_bar["value"] = True
                    ws.close()
            return

        if args.debug and "p" not in data:
            print(f"WebSocket message without bars: {scrub(data)}", file=sys.stderr)

    def on_error(_: websocket.WebSocketApp, error: Any) -> None:
        print(f"WebSocket error: {error}", file=sys.stderr)

    def on_close(_: websocket.WebSocketApp, status_code: Any, message: Any) -> None:
        if not stop_after_first_bar["value"]:
            print(f"WebSocket closed: code={status_code} message={message}", file=sys.stderr)

    ws_url = f"{client.ws_url}/stream/{urllib.parse.quote(stream_id)}?token={urllib.parse.quote(token)}"
    app = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    signal.signal(signal.SIGINT, lambda *_: app.close())
    app.run_forever(ping_interval=30, ping_timeout=10)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001 - this is a CLI POC.
        print(f"fatal: {exc}", file=sys.stderr)
        raise SystemExit(1)
