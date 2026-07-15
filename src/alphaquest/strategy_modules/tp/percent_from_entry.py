from __future__ import annotations

import math


def percent_from_entry_target(
    entry_price: float,
    direction: str,
    pct: float,
    tick_size: float | None = None,
    round_to_tick: bool = True,
) -> float:
    if pct < 0:
        raise ValueError("tp.params.target_pct must be non-negative.")
    raw = entry_price * (1.0 + pct) if direction == "long" else entry_price * (1.0 - pct)
    if not round_to_tick or tick_size is None:
        return raw
    return _round_price(raw, tick_size, "ceil" if direction == "long" else "floor")


class PercentFromEntryTarget:
    name = "percent_from_entry"

    def __init__(self, params: dict):
        self.params = params

    def price(self, entry_price: float, stop_price: float, direction: str, signal=None) -> float:
        tick_size = self.params.get("tick_size")
        return percent_from_entry_target(
            float(entry_price),
            direction,
            float(self.params.get("target_pct", 0.0075)),
            float(tick_size) if tick_size is not None else None,
            bool(self.params.get("round_to_tick", True)),
        )


def _round_price(price: float, tick_size: float, mode: str) -> float:
    if tick_size <= 0:
        raise ValueError("tick_size must be greater than 0.")
    scaled = price / tick_size
    if mode == "ceil":
        return math.ceil(scaled) * tick_size
    if mode == "floor":
        return math.floor(scaled) * tick_size
    raise ValueError(f"Unsupported rounding mode: {mode}")
