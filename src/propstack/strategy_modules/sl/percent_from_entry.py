from __future__ import annotations

import math


def percent_from_entry_stop(
    direction: str,
    entry_price: float,
    pct: float,
    tick_size: float | None = None,
    round_to_tick: bool = True,
) -> float:
    if pct < 0:
        raise ValueError("sl.params.stop_pct must be non-negative.")
    raw = entry_price * (1.0 - pct) if direction == "long" else entry_price * (1.0 + pct)
    if not round_to_tick or tick_size is None:
        return raw
    return _round_price(raw, tick_size, "floor" if direction == "long" else "ceil")


class PercentFromEntryStop:
    name = "percent_from_entry"

    def __init__(self, params: dict):
        self.params = params

    def price(self, signal, direction: str, tick_size: float, entry_price: float | None = None) -> float | None:
        if entry_price is None:
            return None
        return percent_from_entry_stop(
            direction,
            float(entry_price),
            float(self.params.get("stop_pct", 0.003)),
            tick_size,
            bool(self.params.get("round_to_tick", True)),
        )


def _round_price(price: float, tick_size: float, mode: str) -> float:
    if tick_size <= 0:
        raise ValueError("tick_size must be greater than 0.")
    scaled = price / tick_size
    if mode == "floor":
        return math.floor(scaled) * tick_size
    if mode == "ceil":
        return math.ceil(scaled) * tick_size
    raise ValueError(f"Unsupported rounding mode: {mode}")
