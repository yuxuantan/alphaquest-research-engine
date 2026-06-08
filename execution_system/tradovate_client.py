#!/usr/bin/env python3
"""Small stdlib Tradovate REST client used by execution_system."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


REST_BASE_URLS = {
    "demo": "https://demo.tradovateapi.com/v1",
    "live": "https://live.tradovateapi.com/v1",
}
DEFAULT_OAUTH_AUTHORIZE_URL = "https://trader.tradovate.com/oauth"
FUTURES_MONTH_CODES = {
    1: "F",
    2: "G",
    3: "H",
    4: "J",
    5: "K",
    6: "M",
    7: "N",
    8: "Q",
    9: "U",
    10: "V",
    11: "X",
    12: "Z",
}


class TradovateError(RuntimeError):
    """Raised when Tradovate rejects a request or config is incomplete."""


@dataclass(frozen=True)
class TradovateAccount:
    account_id: int
    account_spec: str


class TradovateClient:
    def __init__(self, *, environment: str = "demo", access_token: str, timeout: float = 10.0) -> None:
        self.environment = normalize_environment(environment)
        self.base_url = REST_BASE_URLS[self.environment]
        self.access_token = access_token
        self.timeout = float(timeout)

    def account_list(self) -> list[dict[str, Any]]:
        data = self.get("/account/list")
        if not isinstance(data, list):
            raise TradovateError(f"expected account/list array, got {type(data).__name__}")
        return data

    def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        validate_order_payload(payload, require_brackets=False)
        data = self.post("/order/placeorder", payload)
        return check_tradovate_response(data)

    def place_oso(self, payload: dict[str, Any]) -> dict[str, Any]:
        validate_order_payload(payload, require_brackets=True)
        data = self.post("/order/placeoso", payload)
        return check_tradovate_response(data)

    def get(self, path: str) -> Any:
        return request_json(
            "GET",
            self.base_url + normalize_path(path),
            access_token=self.access_token,
            timeout=self.timeout,
        )

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return request_json(
            "POST",
            self.base_url + normalize_path(path),
            payload=payload,
            access_token=self.access_token,
            timeout=self.timeout,
        )


def request_access_token(config: dict[str, Any]) -> dict[str, Any]:
    environment = normalize_environment(config_value(config, "environment", "TRADOVATE_ENVIRONMENT", "demo"))
    payload = {
        "name": required_config(config, "name", "TRADOVATE_NAME"),
        "password": required_config(config, "password", "TRADOVATE_PASSWORD"),
        "appId": config_value(config, "app_id", "TRADOVATE_APP_ID", "prop-stack-execution"),
        "appVersion": config_value(config, "app_version", "TRADOVATE_APP_VERSION", "1.0"),
        "cid": int(required_config(config, "cid", "TRADOVATE_CID")),
        "sec": required_config(config, "sec", "TRADOVATE_SECRET"),
    }
    device_id = config_value(config, "device_id", "TRADOVATE_DEVICE_ID")
    if device_id:
        payload["deviceId"] = device_id
    return request_json("POST", REST_BASE_URLS[environment] + "/auth/accesstokenrequest", payload=payload)


def request_oauth_token(config: dict[str, Any]) -> dict[str, Any]:
    environment = normalize_environment(config_value(config, "environment", "TRADOVATE_ENVIRONMENT", "demo"))
    payload = {
        "grant_type": config_value(config, "grant_type", "TRADOVATE_OAUTH_GRANT_TYPE", "authorization_code"),
        "code": required_config(config, "oauth_code", "TRADOVATE_OAUTH_CODE"),
        "redirect_uri": required_config(config, "redirect_uri", "TRADOVATE_OAUTH_REDIRECT_URI"),
        "client_id": required_config(config, "client_id", "TRADOVATE_OAUTH_CLIENT_ID"),
        "client_secret": required_config(config, "client_secret", "TRADOVATE_OAUTH_CLIENT_SECRET"),
    }
    http_auth = config_value(config, "http_auth", "TRADOVATE_OAUTH_HTTP_AUTH")
    if http_auth:
        payload["httpAuth"] = http_auth
    return request_json("POST", REST_BASE_URLS[environment] + "/auth/oauthtoken", payload=payload)


def build_oauth_authorize_url(*, client_id: str, redirect_uri: str, state: str | None = None, scope: str | None = None) -> str:
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
    }
    if state:
        query["state"] = state
    if scope:
        query["scope"] = scope
    return DEFAULT_OAUTH_AUTHORIZE_URL + "?" + urllib.parse.urlencode(query)


def client_from_config(config: dict[str, Any]) -> tuple[TradovateClient, dict[str, Any] | None]:
    environment = normalize_environment(config_value(config, "environment", "TRADOVATE_ENVIRONMENT", "demo"))
    timeout = float(config_value(config, "timeout_seconds", "TRADOVATE_TIMEOUT", "10"))
    access_token = config_value(config, "access_token", "TRADOVATE_ACCESS_TOKEN")
    token_response: dict[str, Any] | None = None
    auth_mode = str(config_value(config, "auth_mode", "TRADOVATE_AUTH_MODE", "auto")).lower().replace("-", "_")

    if access_token:
        return TradovateClient(environment=environment, access_token=str(access_token), timeout=timeout), None
    if auth_mode in {"oauth", "oauth_code"} or config_value(config, "oauth_code", "TRADOVATE_OAUTH_CODE"):
        token_response = request_oauth_token(config)
    elif auth_mode in {"credentials", "access_token_request", "api_key"} or config_value(config, "name", "TRADOVATE_NAME"):
        token_response = request_access_token(config)
    else:
        raise TradovateError(
            "missing Tradovate auth; set TRADOVATE_ACCESS_TOKEN, OAuth code settings, or credential/API-key settings"
        )

    access_token = token_response.get("accessToken")
    if not access_token:
        raise TradovateError("Tradovate token response did not include accessToken")
    return TradovateClient(environment=environment, access_token=str(access_token), timeout=timeout), token_response


def resolve_account(client: TradovateClient, config: dict[str, Any]) -> TradovateAccount:
    account_id_raw = config_value(config, "account_id", "TRADOVATE_ACCOUNT_ID")
    account_spec_raw = config_value(config, "account_spec", "TRADOVATE_ACCOUNT_SPEC")
    if account_id_raw and account_spec_raw:
        return TradovateAccount(int(account_id_raw), str(account_spec_raw))

    accounts = client.account_list()
    active_accounts = [account for account in accounts if bool(account.get("active", True))]
    candidates = active_accounts or accounts
    if account_id_raw:
        account_id = int(account_id_raw)
        for account in candidates:
            if int(account.get("id", 0)) == account_id:
                return TradovateAccount(account_id, str(account.get("name", account_id)))
        raise TradovateError(f"Tradovate account_id not found: {account_id}")
    if account_spec_raw:
        account_spec = str(account_spec_raw)
        for account in candidates:
            if str(account.get("name", "")) == account_spec:
                return TradovateAccount(int(account["id"]), account_spec)
        raise TradovateError(f"Tradovate account_spec not found: {account_spec}")
    if len(candidates) == 1:
        account = candidates[0]
        return TradovateAccount(int(account["id"]), str(account["name"]))
    raise TradovateError("set Tradovate account_id/account_spec; account/list returned multiple or zero accounts")


def build_market_oso_payload(
    *,
    account_spec: str | None,
    account_id: int | None,
    action: str,
    symbol: str,
    order_qty: int,
    target_price: Decimal | float | str,
    stop_price: Decimal | float | str,
    time_in_force: str = "Day",
    is_automated: bool = True,
    cl_ord_id: str | None = None,
    custom_tag: str | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    entry_action = tradovate_action(action)
    exit_action = opposite_action(entry_action)
    payload: dict[str, Any] = {
        "accountSpec": account_spec,
        "accountId": account_id,
        "action": entry_action,
        "symbol": symbol,
        "orderQty": int(order_qty),
        "orderType": "Market",
        "timeInForce": time_in_force,
        "isAutomated": bool(is_automated),
        "bracket1": {
            "action": exit_action,
            "orderType": "Limit",
            "price": json_number(target_price),
            "timeInForce": time_in_force,
        },
        "bracket2": {
            "action": exit_action,
            "orderType": "Stop",
            "stopPrice": json_number(stop_price),
            "timeInForce": time_in_force,
        },
    }
    if cl_ord_id:
        payload["clOrdId"] = cl_ord_id
    if custom_tag:
        payload["customTag50"] = custom_tag
    if text:
        payload["text"] = text
    return payload


def prices_from_distances(
    *,
    side: str,
    close_price: Decimal,
    take_profit_points: Decimal,
    stop_loss_points: Decimal,
    tick_size: Decimal,
) -> tuple[Decimal, Decimal]:
    if side.lower() == "buy":
        target = close_price + take_profit_points
        stop = close_price - stop_loss_points
    elif side.lower() == "sell":
        target = close_price - take_profit_points
        stop = close_price + stop_loss_points
    else:
        raise TradovateError(f"unsupported side/action: {side}")
    return round_to_tick(target, tick_size), round_to_tick(stop, tick_size)


def tradovate_contract_symbol(root_symbol: str, expiry: Any, *, year_digits: int = 1) -> str:
    expiry_text = str(expiry or "").strip()
    root = root_symbol.strip().upper()
    if len(expiry_text) < 6 or not expiry_text[:6].isdigit():
        return root
    year = expiry_text[:4]
    month = int(expiry_text[4:6])
    month_code = FUTURES_MONTH_CODES.get(month)
    if not month_code:
        return root
    suffix = year[-1:] if year_digits == 1 else year[-2:]
    return f"{root}{month_code}{suffix}"


def validate_order_payload(payload: dict[str, Any], *, require_brackets: bool) -> None:
    required = ("accountSpec", "accountId", "action", "symbol", "orderQty", "orderType")
    missing = [key for key in required if payload.get(key) in (None, "", 0)]
    if missing:
        raise TradovateError(f"Tradovate order payload is missing: {', '.join(missing)}")
    if require_brackets and not (payload.get("bracket1") and payload.get("bracket2")):
        raise TradovateError("Tradovate OSO payload requires bracket1 and bracket2")


def check_tradovate_response(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise TradovateError(f"unexpected Tradovate response type: {type(data).__name__}")
    failure = data.get("failureReason") or data.get("errorText") or data.get("failureMessage")
    if failure:
        detail = data.get("failureText") or data.get("errorText") or data.get("failureMessage") or ""
        raise TradovateError(f"Tradovate rejected order: {failure} {detail}".strip())
    return data


def request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    access_token: str | None = None,
    timeout: float = 10.0,
) -> Any:
    body = None if payload is None else json.dumps(payload, default=json_default, separators=(",", ":")).encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=float(timeout)) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise TradovateError(f"Tradovate HTTP {exc.code}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise TradovateError(f"could not reach Tradovate: {exc.reason}") from exc
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TradovateError(f"Tradovate returned non-JSON response: {raw[:500]}") from exc


def normalize_environment(value: Any) -> str:
    environment = str(value or "demo").strip().lower()
    if environment not in REST_BASE_URLS:
        raise TradovateError(f"environment must be demo or live, got {value}")
    return environment


def normalize_path(path: str) -> str:
    return path if path.startswith("/") else f"/{path}"


def tradovate_action(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"buy", "long"}:
        return "Buy"
    if normalized in {"sell", "short"}:
        return "Sell"
    if value in {"Buy", "Sell"}:
        return value
    raise TradovateError(f"unsupported action: {value}")


def opposite_action(action: str) -> str:
    normalized = tradovate_action(action)
    return "Sell" if normalized == "Buy" else "Buy"


def round_to_tick(value: Decimal, tick_size: Decimal) -> Decimal:
    ticks = (value / tick_size).to_integral_value()
    return ticks * tick_size


def json_number(value: Decimal | float | int | str) -> int | float:
    decimal = Decimal(str(value))
    if decimal == decimal.to_integral_value():
        return int(decimal)
    return float(decimal)


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return json_number(value)
    raise TypeError(f"object of type {type(value).__name__} is not JSON serializable")


def config_value(config: dict[str, Any], key: str, env_name: str, default: Any = None) -> Any:
    value = config.get(key)
    if value is not None and value != "":
        return value
    return os.getenv(env_name, default)


def required_config(config: dict[str, Any], key: str, env_name: str) -> Any:
    value = config_value(config, key, env_name)
    if value in (None, ""):
        raise TradovateError(f"missing {key}; set config {key} or {env_name}")
    return value
