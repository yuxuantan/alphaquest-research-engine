from __future__ import annotations

import math

from alphaquest.utils.target_rr import MIN_TARGET_R_MULTIPLE


def cost_adjusted_fixed_r_target(
    entry_price: float,
    stop_price: float,
    direction: str,
    r_multiple: float,
    tick_size: float,
    tick_value: float,
    commission_per_contract: float = 0.0,
    slippage_ticks: float = 0.0,
    round_to_tick: bool = True,
) -> float:
    if float(r_multiple) < MIN_TARGET_R_MULTIPLE:
        raise ValueError(f"tp.params.target_r_multiple must be >= {MIN_TARGET_R_MULTIPLE:.1f} reward:risk.")
    if tick_size <= 0:
        raise ValueError("tp.params.tick_size must be greater than 0.")
    if tick_value <= 0:
        raise ValueError("tp.params.tick_value must be greater than 0.")

    slippage_points = tick_size * slippage_ticks
    point_value = tick_value / tick_size
    commission_points = (commission_per_contract * 2) / point_value
    stop_exit_price = stop_price - slippage_points if direction == "long" else stop_price + slippage_points
    risk_after_costs = abs(entry_price - stop_exit_price) + commission_points
    required_target_move = (risk_after_costs * r_multiple) + commission_points + slippage_points

    if direction == "long":
        target = entry_price + required_target_move
        return _round_price(target, tick_size, "ceil") if round_to_tick else target
    if direction == "short":
        target = entry_price - required_target_move
        return _round_price(target, tick_size, "floor") if round_to_tick else target
    raise ValueError(f"Unsupported direction: {direction}")


class CostAdjustedFixedRTarget:
    name = "cost_adjusted_fixed_r"

    def __init__(self, params: dict):
        self.params = params

    def price(self, entry_price: float, stop_price: float, direction: str, signal=None) -> float:
        return cost_adjusted_fixed_r_target(
            float(entry_price),
            float(stop_price),
            direction,
            float(self.params.get("target_r_multiple", 1.0)),
            float(self.params.get("tick_size", 0.25)),
            float(self.params.get("tick_value", 12.50)),
            float(self.params.get("commission_per_contract", 0.0)),
            float(self.params.get("slippage_ticks", 0.0)),
            bool(self.params.get("round_to_tick", True)),
        )


def _round_price(price: float, tick_size: float, mode: str) -> float:
    scaled = price / tick_size
    if mode == "ceil":
        return math.ceil(scaled) * tick_size
    if mode == "floor":
        return math.floor(scaled) * tick_size
    raise ValueError(f"Unsupported rounding mode: {mode}")
