from __future__ import annotations

import math


def fixed_dollar_per_contract_stop(
    direction: str,
    entry_price: float,
    dollars_per_contract: float,
    tick_size: float,
    tick_value: float,
    round_to_tick: bool = True,
) -> float:
    distance = _price_distance(dollars_per_contract, tick_size, tick_value)
    raw = float(entry_price) - distance if direction == "long" else float(entry_price) + distance
    if not round_to_tick:
        return raw
    return _round_price(raw, tick_size, "floor" if direction == "long" else "ceil")


class FixedDollarPerContractStop:
    name = "fixed_dollar_per_contract"

    def __init__(self, params: dict):
        self.params = params

    def price(self, signal, direction: str, tick_size: float, entry_price: float | None = None) -> float | None:
        if entry_price is None:
            return None
        return fixed_dollar_per_contract_stop(
            direction,
            float(entry_price),
            float(self.params.get("dollars_per_contract", 10000.0)),
            float(tick_size),
            float(self.params.get("tick_value", 12.5)),
            bool(self.params.get("round_to_tick", True)),
        )


def _price_distance(dollars_per_contract: float, tick_size: float, tick_value: float) -> float:
    dollars = float(dollars_per_contract)
    tick = float(tick_size)
    value = float(tick_value)
    if dollars <= 0:
        raise ValueError("dollars_per_contract must be greater than 0.")
    if tick <= 0:
        raise ValueError("tick_size must be greater than 0.")
    if value <= 0:
        raise ValueError("tick_value must be greater than 0.")
    return dollars / (value / tick)


def _round_price(price: float, tick_size: float, mode: str) -> float:
    scaled = price / tick_size
    if mode == "floor":
        return math.floor(scaled) * tick_size
    if mode == "ceil":
        return math.ceil(scaled) * tick_size
    raise ValueError(f"Unsupported rounding mode: {mode}")
