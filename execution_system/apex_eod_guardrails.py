#!/usr/bin/env python3
"""
Manual pre-trade guardrails for Apex 50K EOD evaluation/PA accounts.

This script is a compliance gate, not a trading strategy. It blocks a proposed
order before it reaches Tradovate when the order would violate, or get too close
to, Apex-style EOD drawdown, daily loss, position-size, stop/risk, payout, or
market-close constraints.

Account balances and open positions must be kept current from your Apex,
Rithmic, Tradovate, WealthCharts, or broker dashboard. A local guardrail can
only be as accurate as the account snapshot you feed it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import tradovate_client as tradovate


DEFAULT_CONFIG = "apex_50k_eod_guardrails.example.json"
EASTERN = ZoneInfo("America/New_York")

INSTRUMENTS: dict[str, dict[str, Decimal]] = {
    "ES": {
        "tick_size": Decimal("0.25"),
        "point_value": Decimal("50"),
        "standard_equivalent": Decimal("1"),
    },
    "MES": {
        "tick_size": Decimal("0.25"),
        "point_value": Decimal("5"),
        "standard_equivalent": Decimal("0.1"),
    },
    "NQ": {
        "tick_size": Decimal("0.25"),
        "point_value": Decimal("20"),
        "standard_equivalent": Decimal("1"),
    },
    "MNQ": {
        "tick_size": Decimal("0.25"),
        "point_value": Decimal("2"),
        "standard_equivalent": Decimal("0.1"),
    },
}

PA_50K_TIERS = (
    (Decimal("6000"), Decimal("4"), Decimal("3000")),
    (Decimal("3000"), Decimal("4"), Decimal("2000")),
    (Decimal("1500"), Decimal("3"), Decimal("1000")),
    (Decimal("0"), Decimal("2"), Decimal("1000")),
)
PA_50K_MAX_PAYOUTS = (Decimal("1500"), Decimal("1500"), Decimal("2000"), Decimal("2500"), Decimal("2500"), Decimal("3000"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check Apex 50K EOD guardrails before optionally sending a Tradovate order."
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"Guardrail JSON config/snapshot. Defaults to {DEFAULT_CONFIG}.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Show account risk and payout status.")
    status.add_argument("--json", action="store_true", help="Print raw JSON only.")

    check = subparsers.add_parser("check-order", help="Check an order without sending it.")
    add_order_args(check)

    send = subparsers.add_parser("send-order", help="Check an order, then optionally POST it to Tradovate.")
    add_order_args(send)
    add_tradovate_args(send)

    return parser.parse_args()


def add_order_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--side", choices=("buy", "sell"), required=True)
    parser.add_argument("--quantity", type=positive_int, required=True)
    parser.add_argument("--symbol", default="ES")
    parser.add_argument(
        "--accounts",
        nargs="+",
        help="Optional account names to check. Defaults to every enabled account.",
    )
    parser.add_argument(
        "--now",
        help="Override current time. Accepts ISO-8601, interpreted as ET if no timezone is supplied.",
    )
    parser.add_argument("--take-profit-ticks", "--tp-ticks", dest="tp_ticks", type=positive_int)
    parser.add_argument("--stop-loss-ticks", "--sl-ticks", dest="sl_ticks", type=positive_int)
    parser.add_argument("--take-profit-points", "--tp-points", dest="tp_points", type=positive_decimal)
    parser.add_argument("--stop-loss-points", "--sl-points", dest="sl_points", type=positive_decimal)


def add_tradovate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--execute", action="store_true", help="Actually POST to Tradovate. Dry-run by default.")
    parser.add_argument("--environment", choices=("demo", "live"), default=None)
    parser.add_argument("--tradovate-symbol", default=None, help="Tradovate contract symbol, e.g. ESM6. Defaults to --symbol or root+expiry.")
    parser.add_argument("--expiry", default=None, help="YYYYMM expiry used to derive the Tradovate symbol when needed.")
    parser.add_argument("--close", type=positive_decimal, required=True, help="Market/close price used to derive TP/SL bracket prices.")
    parser.add_argument("--account-id", type=positive_int, default=None)
    parser.add_argument("--account-spec", default=None)
    parser.add_argument("--access-token", default=None)
    parser.add_argument("--auth-mode", choices=("auto", "token", "credentials", "oauth-code"), default=None)
    parser.add_argument("--name", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--app-id", default=None)
    parser.add_argument("--app-version", default=None)
    parser.add_argument("--cid", default=None)
    parser.add_argument("--sec", default=None)
    parser.add_argument("--device-id", default=None)
    parser.add_argument("--oauth-code", default=None)
    parser.add_argument("--redirect-uri", default=None)
    parser.add_argument("--client-id", default=None)
    parser.add_argument("--client-secret", default=None)
    parser.add_argument("--time-in-force", default=None)
    parser.add_argument("--cl-ord-id", default=None)
    parser.add_argument("--custom-tag", default=None)
    parser.add_argument("--text", default=None)


def load_config(path: str) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"config is not valid JSON: {path}: {exc}") from exc


def selected_accounts(config: dict[str, Any], names: list[str] | None) -> list[dict[str, Any]]:
    defaults = config.get("defaults", {})
    accounts = []
    requested = set(names or [])
    found: set[str] = set()

    for raw in config.get("accounts", []):
        account = {**defaults, **raw}
        name = str(account.get("name", "")).strip()
        if not name:
            raise SystemExit("every account in config must have a name")
        if names and name not in requested:
            continue
        found.add(name)
        if bool(account.get("enabled", True)):
            accounts.append(account)

    missing = requested - found
    if missing:
        raise SystemExit(f"accounts not found in config: {', '.join(sorted(missing))}")
    if not accounts:
        raise SystemExit("no enabled accounts selected")
    return accounts


def check_order(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    now_et = parse_now(args.now)
    root = instrument_root(args.symbol)
    instrument = instrument_settings(config, root)
    tp_points = distance_points(args.tp_ticks, args.tp_points, instrument["tick_size"], "take profit")
    sl_points = distance_points(args.sl_ticks, args.sl_points, instrument["tick_size"], "stop loss")

    reward_dollars = tp_points * instrument["point_value"] * Decimal(args.quantity)
    risk = order_risk_dollars(config, instrument, sl_points, args.quantity)
    new_exposure = instrument["standard_equivalent"] * Decimal(args.quantity)
    reward_risk = reward_dollars / risk if risk > 0 else Decimal("0")

    order = {
        "symbol": args.symbol.upper(),
        "side": args.side,
        "quantity": args.quantity,
        "take_profit_points": tp_points,
        "stop_loss_points": sl_points,
        "take_profit_ticks": int(tp_points / instrument["tick_size"]),
        "stop_loss_ticks": int(sl_points / instrument["tick_size"]),
        "risk_dollars_per_account": risk,
        "reward_dollars_per_account": reward_dollars,
        "reward_risk": reward_risk,
        "standard_exposure_added": new_exposure,
    }

    results = [
        evaluate_account(config, account, order, new_exposure, risk, reward_risk, now_et)
        for account in selected_accounts(config, args.accounts)
    ]
    blocked = [result for result in results if not result["allowed"]]

    return {
        "allowed": not blocked,
        "checked_at_et": now_et.isoformat(),
        "order": order,
        "accounts": results,
        "blocked_accounts": [result["name"] for result in blocked],
    }


def evaluate_account(
    config: dict[str, Any],
    account: dict[str, Any],
    order: dict[str, Any],
    new_exposure: Decimal,
    risk: Decimal,
    reward_risk: Decimal,
    now_et: dt.datetime,
) -> dict[str, Any]:
    risk_config = config.get("risk", {})
    name = str(account["name"])
    account_type = str(account.get("account_type", "evaluation")).lower()
    side = str(order["side"])

    starting_balance = money(account.get("starting_balance", 50000))
    current_balance = money(account.get("current_balance", starting_balance))
    current_equity = money(account.get("current_equity", current_balance))
    start_of_day_balance = money(account.get("start_of_day_balance", current_balance))
    daily_realized_pnl = money(account.get("daily_realized_pnl", current_balance - start_of_day_balance))
    eod_threshold = calculate_eod_threshold(account)
    daily_loss_limit = effective_daily_loss_limit(account, account_type, current_balance)
    max_contracts = effective_max_contracts(account, account_type, current_balance)
    open_exposure = decimal_value(account.get("open_standard_equivalent", "0"))
    projected_exposure = open_exposure + new_exposure
    projected_equity_at_stop = current_equity - risk
    projected_daily_loss = start_of_day_balance - projected_equity_at_stop
    if projected_daily_loss < 0:
        projected_daily_loss = Decimal("0")

    eod_buffer = money(risk_config.get("personal_eod_buffer", "250"))
    dll_buffer = money(risk_config.get("personal_dll_buffer", "250"))
    max_loss_per_trade = money(risk_config.get("max_loss_per_trade", "250"))
    max_daily_loss = money(risk_config.get("max_daily_loss", "750"))
    min_reward_risk = decimal_value(risk_config.get("min_reward_risk", "1"))
    flat_cutoff = parse_time(str(risk_config.get("flat_cutoff_et", "16:55")))
    lock_after_target = bool(risk_config.get("lock_after_eval_target", True))

    reasons: list[str] = []
    warnings: list[str] = []
    hard_breach_distance = current_equity - eod_threshold
    dll_used = start_of_day_balance - current_equity
    if dll_used < 0:
        dll_used = Decimal("0")

    if bool(account.get("locked", False)):
        reasons.append("account is manually locked in config")
    if current_equity <= eod_threshold:
        reasons.append("current equity is at or below the EOD threshold")
    if projected_equity_at_stop <= eod_threshold:
        reasons.append("stop-loss worst case would touch or breach the EOD threshold")
    if projected_equity_at_stop <= eod_threshold + eod_buffer:
        reasons.append(f"stop-loss worst case would enter the personal EOD buffer (${eod_buffer})")
    if dll_used >= daily_loss_limit:
        reasons.append("daily loss limit is already reached")
    if projected_daily_loss >= daily_loss_limit:
        reasons.append("stop-loss worst case would reach the Apex daily loss limit")
    if projected_daily_loss >= daily_loss_limit - dll_buffer:
        reasons.append(f"stop-loss worst case would enter the personal DLL buffer (${dll_buffer})")
    if projected_daily_loss > max_daily_loss:
        reasons.append(f"stop-loss worst case exceeds configured max daily loss (${max_daily_loss})")
    if risk > max_loss_per_trade:
        reasons.append(f"risk per account (${risk}) exceeds configured max loss per trade (${max_loss_per_trade})")
    if reward_risk < min_reward_risk:
        reasons.append(f"reward:risk {reward_risk:.2f} is below configured minimum {min_reward_risk}")
    if projected_exposure > max_contracts:
        reasons.append(f"projected exposure {projected_exposure} exceeds max contracts {max_contracts}")
    if is_opposite_open_position(account, side):
        reasons.append("order side is opposite the configured open position; hedging/reversal must be handled manually")
    if now_et.time() >= flat_cutoff and now_et.time() < dt.time(18, 0):
        reasons.append(f"new opening trades are blocked after {flat_cutoff.isoformat()} ET")
    if open_exposure > 0 and now_et.time() >= flat_cutoff and now_et.time() < dt.time(18, 0):
        reasons.append("account has open exposure after the flat cutoff")
    if account_type == "evaluation" and lock_after_target and current_balance >= starting_balance + money(account.get("profit_target", 3000)):
        reasons.append("evaluation profit target is reached; further trading is locked")

    if hard_breach_distance < risk * Decimal("3"):
        warnings.append("remaining EOD room is less than 3R of this trade")
    if daily_loss_limit - dll_used < risk * Decimal("2"):
        warnings.append("remaining DLL room is less than 2R of this trade")

    return {
        "name": name,
        "allowed": not reasons,
        "account_type": account_type,
        "platform": str(account.get("platform", "rithmic")),
        "current_balance": current_balance,
        "current_equity": current_equity,
        "start_of_day_balance": start_of_day_balance,
        "daily_realized_pnl": daily_realized_pnl,
        "eod_threshold": eod_threshold,
        "eod_room": current_equity - eod_threshold,
        "projected_equity_at_stop": projected_equity_at_stop,
        "projected_eod_room_at_stop": projected_equity_at_stop - eod_threshold,
        "daily_loss_limit": daily_loss_limit,
        "dll_used": dll_used,
        "dll_remaining": daily_loss_limit - dll_used,
        "projected_daily_loss_at_stop": projected_daily_loss,
        "max_contracts": max_contracts,
        "open_standard_equivalent": open_exposure,
        "projected_standard_equivalent": projected_exposure,
        "reasons": reasons,
        "warnings": warnings,
        "payout": payout_status(account, account_type, current_balance),
    }


def status_report(config: dict[str, Any]) -> dict[str, Any]:
    accounts = selected_accounts(config, None)
    reports = []
    for account in accounts:
        account_type = str(account.get("account_type", "evaluation")).lower()
        current_balance = money(account.get("current_balance", account.get("starting_balance", 50000)))
        eod_threshold = calculate_eod_threshold(account)
        reports.append(
            {
                "name": account["name"],
                "enabled": bool(account.get("enabled", True)),
                "account_type": account_type,
                "platform": str(account.get("platform", "rithmic")),
                "current_balance": current_balance,
                "current_equity": money(account.get("current_equity", current_balance)),
                "eod_threshold": eod_threshold,
                "eod_room": money(account.get("current_equity", current_balance)) - eod_threshold,
                "daily_loss_limit": effective_daily_loss_limit(account, account_type, current_balance),
                "max_contracts": effective_max_contracts(account, account_type, current_balance),
                "open_standard_equivalent": decimal_value(account.get("open_standard_equivalent", "0")),
                "evaluation_pass_ready": evaluation_pass_ready(account, current_balance),
                "payout": payout_status(account, account_type, current_balance),
            }
        )
    return {"accounts": reports}


def build_tradovate_payload(
    config: dict[str, Any],
    args: argparse.Namespace,
    check: dict[str, Any],
    account: tradovate.TradovateAccount | None = None,
) -> dict[str, Any]:
    tv_config = tradovate_config(config, args)
    symbol = str(tv_config.get("symbol") or args.tradovate_symbol or args.symbol).upper()
    if not args.tradovate_symbol and args.expiry:
        symbol = tradovate.tradovate_contract_symbol(instrument_root(args.symbol), args.expiry)

    target_price, stop_price = tradovate.prices_from_distances(
        side=check["order"]["side"],
        close_price=args.close,
        take_profit_points=decimal_value(check["order"]["take_profit_points"]),
        stop_loss_points=decimal_value(check["order"]["stop_loss_points"]),
        tick_size=instrument_settings(config, instrument_root(args.symbol))["tick_size"],
    )
    account_spec = account.account_spec if account else tv_config.get("account_spec")
    account_id = account.account_id if account else tv_config.get("account_id")
    return tradovate.build_market_oso_payload(
        account_spec=str(account_spec) if account_spec else None,
        account_id=int(account_id) if account_id else None,
        action=check["order"]["side"],
        symbol=symbol,
        order_qty=int(check["order"]["quantity"]),
        target_price=target_price,
        stop_price=stop_price,
        time_in_force=str(tv_config.get("time_in_force", "Day")),
        cl_ord_id=tv_config.get("cl_ord_id"),
        custom_tag=tv_config.get("custom_tag"),
        text=tv_config.get("text"),
    )


def tradovate_config(config: dict[str, Any], args: argparse.Namespace | None = None) -> dict[str, Any]:
    tv_config = dict(config.get("tradovate", {}))
    if args is None:
        return tv_config
    mapping = {
        "environment": "environment",
        "tradovate_symbol": "symbol",
        "account_id": "account_id",
        "account_spec": "account_spec",
        "access_token": "access_token",
        "auth_mode": "auth_mode",
        "name": "name",
        "password": "password",
        "app_id": "app_id",
        "app_version": "app_version",
        "cid": "cid",
        "sec": "sec",
        "device_id": "device_id",
        "oauth_code": "oauth_code",
        "redirect_uri": "redirect_uri",
        "client_id": "client_id",
        "client_secret": "client_secret",
        "time_in_force": "time_in_force",
        "cl_ord_id": "cl_ord_id",
        "custom_tag": "custom_tag",
        "text": "text",
    }
    for arg_name, key in mapping.items():
        value = getattr(args, arg_name, None)
        if value not in (None, ""):
            tv_config[key] = value
    return tv_config


def calculate_eod_threshold(account: dict[str, Any]) -> Decimal:
    starting = money(account.get("starting_balance", 50000))
    max_drawdown = money(account.get("max_eod_drawdown", 2000))
    highest_eod = max(money(account.get("highest_eod_balance", starting)), starting)
    initial = starting - max_drawdown
    candidate = max(initial, highest_eod - max_drawdown)
    platform = str(account.get("platform", "rithmic")).lower()
    account_type = str(account.get("account_type", "evaluation")).lower()

    cap: Decimal | None = None
    if account_type == "pa":
        cap = starting + Decimal("100")
    elif platform in {"rithmic", "wealthcharts"}:
        cap = starting + money(account.get("profit_target", 3000))
    if cap is not None:
        candidate = min(candidate, cap)

    dashboard_threshold = account.get("eod_threshold")
    if dashboard_threshold is not None:
        candidate = max(candidate, money(dashboard_threshold))
    return candidate


def effective_daily_loss_limit(account: dict[str, Any], account_type: str, current_balance: Decimal) -> Decimal:
    if account_type != "pa":
        return money(account.get("daily_loss_limit", 1000))
    profit = current_balance - money(account.get("starting_balance", 50000))
    for floor, _contracts, dll in PA_50K_TIERS:
        if profit >= floor:
            return dll
    return Decimal("1000")


def effective_max_contracts(account: dict[str, Any], account_type: str, current_balance: Decimal) -> Decimal:
    if account_type != "pa":
        return decimal_value(account.get("max_contracts", "6"))
    profit = current_balance - money(account.get("starting_balance", 50000))
    for floor, contracts, _dll in PA_50K_TIERS:
        if profit >= floor:
            return contracts
    return Decimal("2")


def evaluation_pass_ready(account: dict[str, Any], current_balance: Decimal) -> bool:
    if str(account.get("account_type", "evaluation")).lower() != "evaluation":
        return False
    starting = money(account.get("starting_balance", 50000))
    target = money(account.get("profit_target", 3000))
    return current_balance >= starting + target


def payout_status(account: dict[str, Any], account_type: str, current_balance: Decimal) -> dict[str, Any]:
    if account_type != "pa":
        return {"applicable": False}

    starting = money(account.get("starting_balance", 50000))
    safety_net = starting + money(account.get("max_eod_drawdown", 2000)) + Decimal("100")
    minimum_balance = safety_net + Decimal("500")
    qualified_days = int(account.get("qualified_days", 0))
    payout_count = int(account.get("payout_count", 0))
    cycle_profit = money(account.get("payout_cycle_profit", current_balance - starting))
    largest_day = money(account.get("largest_profitable_day", 0))
    consistency_ratio = largest_day / cycle_profit if cycle_profit > 0 else Decimal("0")
    next_max_payout = PA_50K_MAX_PAYOUTS[payout_count] if payout_count < len(PA_50K_MAX_PAYOUTS) else Decimal("0")
    available_above_safety = max(Decimal("0"), current_balance - safety_net)

    reasons = []
    if qualified_days < 5:
        reasons.append("fewer than 5 qualifying profit days")
    if current_balance < minimum_balance:
        reasons.append("balance is below the minimum payout request balance")
    if consistency_ratio >= Decimal("0.5"):
        reasons.append("largest profitable day is 50% or more of cycle profit")
    if payout_count >= 6:
        reasons.append("maximum six payouts already reached")

    return {
        "applicable": True,
        "ready": not reasons,
        "qualified_days": qualified_days,
        "min_qualified_days": 5,
        "safety_net": safety_net,
        "minimum_balance_to_request": minimum_balance,
        "available_above_safety_net": available_above_safety,
        "minimum_request": Decimal("500"),
        "next_max_payout": next_max_payout,
        "consistency_ratio": consistency_ratio,
        "payout_count": payout_count,
        "reasons": reasons,
    }


def order_risk_dollars(
    config: dict[str, Any],
    instrument: dict[str, Decimal],
    stop_points: Decimal,
    quantity: int,
) -> Decimal:
    risk_config = config.get("risk", {})
    slippage_ticks = decimal_value(risk_config.get("slippage_ticks", "1"))
    cost_per_contract = money(risk_config.get("round_turn_cost_per_contract", "5"))
    price_risk = (stop_points + slippage_ticks * instrument["tick_size"]) * instrument["point_value"]
    return (price_risk + cost_per_contract) * Decimal(quantity)


def is_opposite_open_position(account: dict[str, Any], side: str) -> bool:
    open_side = str(account.get("open_side", "flat")).lower()
    open_exposure = decimal_value(account.get("open_standard_equivalent", "0"))
    if open_exposure <= 0 or open_side in {"", "flat", "none"}:
        return False
    return (open_side == "long" and side == "sell") or (open_side == "short" and side == "buy")


def instrument_root(symbol: str) -> str:
    upper = symbol.upper()
    for root in sorted(INSTRUMENTS, key=len, reverse=True):
        if upper.startswith(root):
            return root
    raise SystemExit(f"unsupported symbol {symbol}; add it to instruments in config")


def instrument_settings(config: dict[str, Any], root: str) -> dict[str, Decimal]:
    raw = {**INSTRUMENTS[root], **config.get("instruments", {}).get(root, {})}
    return {
        "tick_size": decimal_value(raw["tick_size"]),
        "point_value": decimal_value(raw["point_value"]),
        "standard_equivalent": decimal_value(raw["standard_equivalent"]),
    }


def distance_points(
    ticks: int | None,
    points: Decimal | None,
    tick_size: Decimal,
    label: str,
) -> Decimal:
    if (ticks is None) == (points is None):
        raise SystemExit(f"provide exactly one of {label} ticks or {label} points")
    if ticks is not None:
        return Decimal(ticks) * tick_size
    assert points is not None
    raw_ticks = points / tick_size
    if raw_ticks != raw_ticks.to_integral_value():
        raise SystemExit(f"{label} points ({points}) must divide evenly by tick size ({tick_size})")
    return points


def parse_now(value: str | None) -> dt.datetime:
    if not value:
        return dt.datetime.now(EASTERN)
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=EASTERN)
    return parsed.astimezone(EASTERN)


def parse_time(value: str) -> dt.time:
    hour, minute = value.split(":", 1)
    return dt.time(int(hour), int(minute))


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def positive_decimal(value: str) -> Decimal:
    parsed = decimal_value(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def decimal_value(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"not a decimal number: {value}") from exc


def money(value: Any) -> Decimal:
    return decimal_value(value).quantize(Decimal("0.01"))


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    raise TypeError(f"object of type {type(value).__name__} is not JSON serializable")


def print_report(report: dict[str, Any]) -> None:
    print(json.dumps(report, indent=2, sort_keys=True, default=json_default))


def print_status(report: dict[str, Any]) -> None:
    for account in report["accounts"]:
        line = (
            f"{account['name']}: balance=${account['current_balance']} "
            f"equity=${account['current_equity']} "
            f"EOD=${account['eod_threshold']} "
            f"room=${account['eod_room']} "
            f"DLL=${account['daily_loss_limit']} "
            f"max={account['max_contracts']} contracts"
        )
        print(line)
        if account["evaluation_pass_ready"]:
            print("  evaluation target reached; stop trading this eval unless Apex confirms otherwise")
        payout = account["payout"]
        if payout.get("applicable"):
            ready = "ready" if payout["ready"] else "not ready"
            print(
                f"  payout {ready}: days={payout['qualified_days']}/5 "
                f"min_balance=${payout['minimum_balance_to_request']} "
                f"consistency={payout['consistency_ratio']:.2%}"
            )
            for reason in payout["reasons"]:
                print(f"  - {reason}")


def main() -> int:
    args = parse_args()
    config = load_config(args.config)

    if args.command == "status":
        report = status_report(config)
        if args.json:
            print_report(report)
        else:
            print_status(report)
        return 0

    report = check_order(config, args)
    print_report(report)
    if not report["allowed"]:
        return 2

    if args.command == "send-order":
        payload = build_tradovate_payload(config, args, report)
        print("Guardrails passed. Tradovate order payload:")
        print_report(payload)
        if not args.execute:
            print("Dry run only. Add --execute to POST this order to Tradovate.", file=sys.stderr)
            return 0
        tv_config = tradovate_config(config, args)
        client, _token_response = tradovate.client_from_config(tv_config)
        if not payload.get("accountSpec") or not payload.get("accountId"):
            account = tradovate.resolve_account(client, tv_config)
            payload = build_tradovate_payload(config, args, report, account)
        response = client.place_oso(payload)
        print_report({"endpoint": f"{client.base_url}/order/placeoso", "request": payload, "response": response})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
