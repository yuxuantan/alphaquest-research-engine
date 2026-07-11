from __future__ import annotations

import math


def prop_fixed_fraction_r_target(
    entry_price: float,
    stop_price: float,
    direction: str,
    target_r_fraction: float,
    *,
    tick_size: float | None = None,
    round_to_tick: bool = False,
) -> float:
    fraction = float(target_r_fraction)
    if fraction <= 0:
        raise ValueError("target_r_fraction must be greater than 0.")
    risk = abs(entry_price - stop_price)
    if direction == "long":
        target = entry_price + risk * fraction
        return _round_profit_target_to_tick(target, "long", tick_size, round_to_tick)
    target = entry_price - risk * fraction
    return _round_profit_target_to_tick(target, "short", tick_size, round_to_tick)


def _round_profit_target_to_tick(
    price: float,
    direction: str,
    tick_size: float | None,
    round_to_tick: bool,
) -> float:
    if not round_to_tick:
        return price
    tick = float(tick_size or 0)
    if tick <= 0:
        raise ValueError("tick_size must be greater than 0 when round_to_tick is true.")
    scaled = price / tick
    if direction == "long":
        return round(math.ceil(scaled - 1e-12) * tick, 10)
    return round(math.floor(scaled + 1e-12) * tick, 10)


class PropFixedFractionRTarget:
    name = "prop_fixed_fraction_r"

    def __init__(self, params: dict):
        self.params = params

    def price(self, entry_price: float, stop_price: float, direction: str, signal=None) -> float:
        return prop_fixed_fraction_r_target(
            entry_price,
            stop_price,
            direction,
            float(self.params.get("target_r_fraction", 0.5)),
            tick_size=self.params.get("tick_size"),
            round_to_tick=bool(self.params.get("round_to_tick", False)),
        )
