from __future__ import annotations

import math


def fixed_dollar_per_contract_target(
    entry_price: float,
    direction: str,
    dollars_per_contract: float,
    tick_size: float,
    tick_value: float,
    round_to_tick: bool = True,
) -> float:
    distance = _price_distance(dollars_per_contract, tick_size, tick_value)
    raw = float(entry_price) + distance if direction == "long" else float(entry_price) - distance
    if not round_to_tick:
        return raw
    return _round_price(raw, tick_size, "ceil" if direction == "long" else "floor")


class FixedDollarPerContractTarget:
    name = "fixed_dollar_per_contract"

    def __init__(self, params: dict):
        self.params = params

    def price(self, entry_price: float, stop_price: float, direction: str, signal=None) -> float:
        return fixed_dollar_per_contract_target(
            float(entry_price),
            direction,
            float(self.params.get("dollars_per_contract", 10000.0)),
            float(self.params.get("tick_size", 0.25)),
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
    if mode == "ceil":
        return math.ceil(scaled) * tick_size
    if mode == "floor":
        return math.floor(scaled) * tick_size
    raise ValueError(f"Unsupported rounding mode: {mode}")
