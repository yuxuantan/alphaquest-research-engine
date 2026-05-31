from __future__ import annotations


def fixed_r_target(entry_price: float, stop_price: float, direction: str, r_multiple: float) -> float:
    risk = abs(entry_price - stop_price)
    if direction == "long":
        return entry_price + risk * r_multiple
    return entry_price - risk * r_multiple
