#!/usr/bin/env python3
"""
Trigger an ES market order through a Proteryx Auto Trader webhook with TP/SL.

The script sends the documented TradingView/Auto Trader style JSON payload to:
    https://api.proteryx.com/tradingview/auto-traders/alert

By default this is a dry run and only prints the payload. Add --execute to send it.

Required Proteryx setup:
    1. Create/configure an Auto Trader in Proteryx.
    2. Connect the intended broker/account or portfolio route.
    3. Copy the Auto Trader strategy UUID into PROTERYX_STRATEGY_UUID or pass
       --strategy-uuid.
    4. Confirm the symbol/contract format expected by your Proteryx setup.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any


DEFAULT_WEBHOOK_URL = "https://api.proteryx.com/tradingview/auto-traders/alert"
DEFAULT_ROUTE = "selected_accounts"
DEFAULT_ES_TICK_SIZE = Decimal("0.25")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Send a Proteryx webhook payload for an ES market order with attached "
            "take-profit and stop-loss distances."
        )
    )
    parser.add_argument(
        "--side",
        choices=("buy", "sell"),
        required=True,
        help="Entry side for the market order.",
    )
    parser.add_argument(
        "--quantity",
        type=positive_int,
        default=env_int("PROTERYX_QUANTITY", 1),
        help="Contract quantity. Defaults to PROTERYX_QUANTITY or 1.",
    )
    parser.add_argument(
        "--symbol",
        default=os.getenv("PROTERYX_SYMBOL", "ES"),
        help=(
            "Futures symbol/contract as configured in Proteryx, for example ES, "
            "ESM6, or another broker-mapped ES symbol. Defaults to PROTERYX_SYMBOL "
            "or ES."
        ),
    )
    parser.add_argument(
        "--strategy-uuid",
        default=os.getenv("PROTERYX_STRATEGY_UUID"),
        help="Proteryx Auto Trader strategy UUID. Defaults to PROTERYX_STRATEGY_UUID.",
    )
    parser.add_argument(
        "--portfolio",
        default=os.getenv("PROTERYX_PORTFOLIO"),
        help="Optional Proteryx portfolio name. Defaults to PROTERYX_PORTFOLIO.",
    )
    parser.add_argument(
        "--route",
        default=os.getenv("PROTERYX_ROUTE", DEFAULT_ROUTE),
        help=f"Proteryx route value. Defaults to PROTERYX_ROUTE or {DEFAULT_ROUTE}.",
    )
    parser.add_argument(
        "--webhook-url",
        default=os.getenv("PROTERYX_WEBHOOK_URL", DEFAULT_WEBHOOK_URL),
        help="Webhook endpoint. Defaults to PROTERYX_WEBHOOK_URL or Proteryx's Auto Trader endpoint.",
    )
    parser.add_argument(
        "--timeout",
        type=positive_decimal,
        default=Decimal(os.getenv("PROTERYX_TIMEOUT", "10")),
        help="HTTP timeout in seconds. Defaults to PROTERYX_TIMEOUT or 10.",
    )
    parser.add_argument(
        "--exchange",
        default=os.getenv("PROTERYX_EXCHANGE", "CME"),
        help="Optional exchange/source context. Defaults to PROTERYX_EXCHANGE or CME.",
    )
    parser.add_argument(
        "--close",
        type=positive_decimal,
        default=env_decimal("PROTERYX_CLOSE"),
        help="Optional current close/market price context sent as the close field.",
    )
    parser.add_argument(
        "--client-tag",
        default=os.getenv("PROTERYX_CLIENT_TAG"),
        help="Optional client-side tag included in the payload for log tracing.",
    )
    parser.add_argument(
        "--extra-json",
        help=(
            "Optional JSON object merged into the payload for custom Proteryx field "
            "mappings, for example '{\"account\":\"Sim\"}'."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually POST to Proteryx. Without this flag the script only prints the payload.",
    )

    risk = parser.add_argument_group("TP/SL distance")
    risk.add_argument(
        "--take-profit-ticks",
        "--tp-ticks",
        dest="take_profit_ticks",
        type=positive_int,
        help="Take-profit distance in ticks.",
    )
    risk.add_argument(
        "--stop-loss-ticks",
        "--sl-ticks",
        dest="stop_loss_ticks",
        type=positive_int,
        help="Stop-loss distance in ticks.",
    )
    risk.add_argument(
        "--take-profit-points",
        "--tp-points",
        dest="take_profit_points",
        type=positive_decimal,
        help="Take-profit distance in ES points. Converted to ticks using --tick-size.",
    )
    risk.add_argument(
        "--stop-loss-points",
        "--sl-points",
        dest="stop_loss_points",
        type=positive_decimal,
        help="Stop-loss distance in ES points. Converted to ticks using --tick-size.",
    )
    risk.add_argument(
        "--tick-size",
        type=positive_decimal,
        default=env_decimal("PROTERYX_TICK_SIZE", DEFAULT_ES_TICK_SIZE),
        help="Tick size for point conversion. Defaults to PROTERYX_TICK_SIZE or 0.25.",
    )

    args = parser.parse_args()
    validate_args(parser, args)
    return args


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if not args.strategy_uuid:
        parser.error("missing --strategy-uuid or PROTERYX_STRATEGY_UUID")
    if not args.symbol.strip():
        parser.error("missing --symbol")
    if not args.webhook_url.startswith(("http://", "https://")):
        parser.error("--webhook-url must start with http:// or https://")

    has_tp_ticks = args.take_profit_ticks is not None
    has_tp_points = args.take_profit_points is not None
    has_sl_ticks = args.stop_loss_ticks is not None
    has_sl_points = args.stop_loss_points is not None
    if has_tp_ticks == has_tp_points:
        parser.error("provide exactly one of --take-profit-ticks or --take-profit-points")
    if has_sl_ticks == has_sl_points:
        parser.error("provide exactly one of --stop-loss-ticks or --stop-loss-points")

    if args.extra_json is not None:
        extra = parse_extra_json(args.extra_json, parser)
        if not isinstance(extra, dict):
            parser.error("--extra-json must be a JSON object")
        args.extra_json = extra


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    take_profit_ticks = ticks_from_distance(
        ticks=args.take_profit_ticks,
        points=args.take_profit_points,
        tick_size=args.tick_size,
        label="take profit",
    )
    stop_loss_ticks = ticks_from_distance(
        ticks=args.stop_loss_ticks,
        points=args.stop_loss_points,
        tick_size=args.tick_size,
        label="stop loss",
    )

    payload: dict[str, Any] = {
        "strategy_uuid": args.strategy_uuid,
        "time_now": dt.datetime.now(dt.timezone.utc).isoformat(),
        "symbol": args.symbol.strip(),
        "side": args.side,
        "quantity": args.quantity,
        "orderType": "market",
        "takeProfitTicks": take_profit_ticks,
        "stopLossTicks": stop_loss_ticks,
        "route": args.route,
    }

    if args.portfolio:
        payload["portfolio"] = args.portfolio
    if args.exchange:
        payload["exchange"] = args.exchange
    if args.close is not None:
        payload["close"] = decimal_to_json_number(args.close)
    if args.client_tag:
        payload["clientTag"] = args.client_tag
    if args.extra_json:
        payload.update(args.extra_json)

    return payload


def post_json(url: str, payload: dict[str, Any], timeout: Decimal) -> tuple[int, str]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "User-Agent": "proteryx-es-market-bracket/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=float(timeout)) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Proteryx returned HTTP {exc.code}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Proteryx: {exc.reason}") from exc


def ticks_from_distance(
    *,
    ticks: int | None,
    points: Decimal | None,
    tick_size: Decimal,
    label: str,
) -> int:
    if ticks is not None:
        return ticks
    assert points is not None
    raw_ticks = points / tick_size
    integral = raw_ticks.to_integral_value()
    if raw_ticks != integral:
        raise SystemExit(
            f"{label} points ({points}) must divide evenly by tick size ({tick_size}); "
            f"computed {raw_ticks} ticks"
        )
    return int(integral)


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def parse_extra_json(value: str, parser: argparse.ArgumentParser) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        parser.error(f"--extra-json is not valid JSON: {exc}")


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def positive_decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("must be a decimal number") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return positive_int(value)


def env_decimal(name: str, default: Decimal | None = None) -> Decimal | None:
    value = os.getenv(name)
    if value is None:
        return default
    return positive_decimal(value)


def decimal_to_json_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)

    if payload["symbol"] in {"ES", "MES", "NQ", "MNQ"}:
        print(
            f"Warning: using root symbol {payload['symbol']}. Confirm your Proteryx "
            "automation maps it to the active contract expected by your broker.",
            file=sys.stderr,
        )

    if not args.execute:
        print("Dry run only. Add --execute to POST this payload to Proteryx.", file=sys.stderr)
        print_json(payload)
        return 0

    status, response_body = post_json(args.webhook_url, payload, args.timeout)
    print(f"POST {args.webhook_url} -> HTTP {status}")
    if response_body:
        try:
            print(json.dumps(json.loads(response_body), indent=2, sort_keys=True))
        except json.JSONDecodeError:
            print(response_body)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
