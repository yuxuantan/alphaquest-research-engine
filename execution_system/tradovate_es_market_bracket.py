#!/usr/bin/env python3
"""Place a guarded ES market bracket order through Tradovate REST."""

from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal, InvalidOperation
from typing import Any

import tradovate_client as tradovate


DEFAULT_TICK_SIZE = Decimal("0.25")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Authenticate with Tradovate and place market OSO bracket orders.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    auth_url = subparsers.add_parser("auth-url", help="Print the Tradovate OAuth authorization URL.")
    auth_url.add_argument("--client-id", default=os.getenv("TRADOVATE_OAUTH_CLIENT_ID"), required=False)
    auth_url.add_argument("--redirect-uri", default=os.getenv("TRADOVATE_OAUTH_REDIRECT_URI"), required=False)
    auth_url.add_argument("--state", default=os.getenv("TRADOVATE_OAUTH_STATE"))
    auth_url.add_argument("--scope", default=os.getenv("TRADOVATE_OAUTH_SCOPE"))

    accounts = subparsers.add_parser("accounts", help="Authenticate and list Tradovate accounts.")
    add_auth_args(accounts)

    send = subparsers.add_parser("send-order", help="Dry-run or execute a Tradovate market bracket order.")
    add_auth_args(send)
    add_account_args(send)
    send.add_argument("--side", choices=("buy", "sell"), required=True)
    send.add_argument("--quantity", type=positive_int, default=env_int("TRADOVATE_QUANTITY", 1))
    send.add_argument("--symbol", default=os.getenv("TRADOVATE_SYMBOL"), help="Tradovate contract symbol, e.g. ESM6.")
    send.add_argument("--root-symbol", default=os.getenv("TRADOVATE_ROOT_SYMBOL", "ES"))
    send.add_argument("--expiry", default=os.getenv("TRADOVATE_EXPIRY"), help="YYYYMM expiry used when --symbol is omitted.")
    send.add_argument("--close", type=positive_decimal, default=env_decimal("TRADOVATE_CLOSE"))
    send.add_argument("--target-price", type=positive_decimal)
    send.add_argument("--stop-price", type=positive_decimal)
    send.add_argument("--take-profit-ticks", "--tp-ticks", dest="tp_ticks", type=positive_int)
    send.add_argument("--stop-loss-ticks", "--sl-ticks", dest="sl_ticks", type=positive_int)
    send.add_argument("--take-profit-points", "--tp-points", dest="tp_points", type=positive_decimal)
    send.add_argument("--stop-loss-points", "--sl-points", dest="sl_points", type=positive_decimal)
    send.add_argument("--tick-size", type=positive_decimal, default=env_decimal("TRADOVATE_TICK_SIZE", DEFAULT_TICK_SIZE))
    send.add_argument("--time-in-force", default=os.getenv("TRADOVATE_TIME_IN_FORCE", "Day"))
    send.add_argument("--cl-ord-id", default=os.getenv("TRADOVATE_CL_ORD_ID"))
    send.add_argument("--custom-tag", default=os.getenv("TRADOVATE_CUSTOM_TAG"))
    send.add_argument("--text", default=os.getenv("TRADOVATE_ORDER_TEXT"))
    send.add_argument("--execute", action="store_true", help="Actually POST to Tradovate. Dry-run by default.")

    args = parser.parse_args()
    validate_args(parser, args)
    return args


def add_auth_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--environment", choices=("demo", "live"), default=os.getenv("TRADOVATE_ENVIRONMENT", "demo"))
    parser.add_argument("--timeout", type=positive_decimal, default=env_decimal("TRADOVATE_TIMEOUT", Decimal("10")))
    parser.add_argument("--access-token", default=os.getenv("TRADOVATE_ACCESS_TOKEN"))
    parser.add_argument("--auth-mode", choices=("auto", "token", "credentials", "oauth-code"), default=os.getenv("TRADOVATE_AUTH_MODE", "auto"))
    parser.add_argument("--name", default=os.getenv("TRADOVATE_NAME"), help="Tradovate username/account name for accessTokenRequest.")
    parser.add_argument("--password", default=os.getenv("TRADOVATE_PASSWORD"), help="Dedicated API password for accessTokenRequest.")
    parser.add_argument("--app-id", default=os.getenv("TRADOVATE_APP_ID", "prop-stack-execution"))
    parser.add_argument("--app-version", default=os.getenv("TRADOVATE_APP_VERSION", "1.0"))
    parser.add_argument("--cid", default=os.getenv("TRADOVATE_CID"))
    parser.add_argument("--sec", default=os.getenv("TRADOVATE_SECRET"))
    parser.add_argument("--device-id", default=os.getenv("TRADOVATE_DEVICE_ID"))
    parser.add_argument("--oauth-code", default=os.getenv("TRADOVATE_OAUTH_CODE"))
    parser.add_argument("--redirect-uri", default=os.getenv("TRADOVATE_OAUTH_REDIRECT_URI"))
    parser.add_argument("--client-id", default=os.getenv("TRADOVATE_OAUTH_CLIENT_ID"))
    parser.add_argument("--client-secret", default=os.getenv("TRADOVATE_OAUTH_CLIENT_SECRET"))


def add_account_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--account-id", type=int, default=env_int_or_none("TRADOVATE_ACCOUNT_ID"))
    parser.add_argument("--account-spec", default=os.getenv("TRADOVATE_ACCOUNT_SPEC"))


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.command == "auth-url":
        if not args.client_id:
            parser.error("auth-url requires --client-id or TRADOVATE_OAUTH_CLIENT_ID")
        if not args.redirect_uri:
            parser.error("auth-url requires --redirect-uri or TRADOVATE_OAUTH_REDIRECT_URI")
    if args.command != "send-order":
        return
    has_prices = args.target_price is not None or args.stop_price is not None
    if has_prices and not (args.target_price is not None and args.stop_price is not None):
        parser.error("provide both --target-price and --stop-price, or neither")
    if not has_prices:
        if args.close is None:
            parser.error("missing --close when deriving TP/SL prices from distances")
        if (args.tp_ticks is None) == (args.tp_points is None):
            parser.error("provide exactly one of --take-profit-ticks or --take-profit-points")
        if (args.sl_ticks is None) == (args.sl_points is None):
            parser.error("provide exactly one of --stop-loss-ticks or --stop-loss-points")
    if not args.symbol and not args.expiry:
        parser.error("provide --symbol or --expiry")


def main() -> int:
    args = parse_args()
    if args.command == "auth-url":
        print(tradovate.build_oauth_authorize_url(
            client_id=args.client_id,
            redirect_uri=args.redirect_uri,
            state=args.state,
            scope=args.scope,
        ))
        return 0

    auth_config = auth_config_from_args(args)
    if args.command == "accounts":
        client, _token_response = tradovate.client_from_config(auth_config)
        print_json(client.account_list())
        return 0

    assert args.command == "send-order"
    symbol = args.symbol or tradovate.tradovate_contract_symbol(args.root_symbol, args.expiry)
    target_price, stop_price = order_prices(args)

    account_spec = args.account_spec
    account_id = args.account_id
    payload = tradovate.build_market_oso_payload(
        account_spec=account_spec,
        account_id=account_id,
        action=args.side,
        symbol=symbol,
        order_qty=args.quantity,
        target_price=target_price,
        stop_price=stop_price,
        time_in_force=args.time_in_force,
        cl_ord_id=args.cl_ord_id,
        custom_tag=args.custom_tag,
        text=args.text,
    )

    if not args.execute:
        print("Dry run only. Add --execute to POST this order to Tradovate.", file=sys.stderr)
        print_json(payload)
        return 0

    client, _token_response = tradovate.client_from_config(auth_config)
    if not account_spec or not account_id:
        account = tradovate.resolve_account(client, account_config_from_args(args))
        payload["accountSpec"] = account.account_spec
        payload["accountId"] = account.account_id
    response = client.place_oso(payload)
    print_json({"endpoint": f"{client.base_url}/order/placeoso", "request": payload, "response": response})
    return 0


def auth_config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "environment": args.environment,
        "timeout_seconds": args.timeout,
        "access_token": args.access_token,
        "auth_mode": args.auth_mode,
        "name": args.name,
        "password": args.password,
        "app_id": args.app_id,
        "app_version": args.app_version,
        "cid": args.cid,
        "sec": args.sec,
        "device_id": args.device_id,
        "oauth_code": args.oauth_code,
        "redirect_uri": args.redirect_uri,
        "client_id": args.client_id,
        "client_secret": args.client_secret,
    }


def account_config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {"account_id": args.account_id, "account_spec": args.account_spec}


def order_prices(args: argparse.Namespace) -> tuple[Decimal, Decimal]:
    if args.target_price is not None and args.stop_price is not None:
        return args.target_price, args.stop_price
    tp_points = distance_points(args.tp_ticks, args.tp_points, args.tick_size, "take profit")
    sl_points = distance_points(args.sl_ticks, args.sl_points, args.tick_size, "stop loss")
    return tradovate.prices_from_distances(
        side=args.side,
        close_price=args.close,
        take_profit_points=tp_points,
        stop_loss_points=sl_points,
        tick_size=args.tick_size,
    )


def distance_points(ticks: int | None, points: Decimal | None, tick_size: Decimal, label: str) -> Decimal:
    if ticks is not None:
        return Decimal(ticks) * tick_size
    assert points is not None
    raw_ticks = points / tick_size
    if raw_ticks != raw_ticks.to_integral_value():
        raise SystemExit(f"{label} points ({points}) must divide evenly by tick size ({tick_size})")
    return points


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=tradovate.json_default))


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
        parsed = Decimal(str(value))
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


def env_int_or_none(name: str) -> int | None:
    value = os.getenv(name)
    if value is None:
        return None
    return positive_int(value)


def env_decimal(name: str, default: Decimal | None = None) -> Decimal | None:
    value = os.getenv(name)
    if value is None:
        return default
    return positive_decimal(value)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except tradovate.TradovateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
