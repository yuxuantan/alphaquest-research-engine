from __future__ import annotations


def entry_price(open_price: float, direction: str, tick_size: float, slippage_ticks: float) -> float:
    slip = tick_size * slippage_ticks
    return open_price + slip if direction == "long" else open_price - slip


def exit_price(price: float, direction: str, tick_size: float, slippage_ticks: float) -> float:
    slip = tick_size * slippage_ticks
    return price - slip if direction == "long" else price + slip


def stop_target_hit(bar, direction: str, stop_price: float, target_price: float) -> tuple[str | None, float | None]:
    if direction == "long":
        stop_hit = bar["low"] <= stop_price
        target_hit = bar["high"] >= target_price
    else:
        stop_hit = bar["high"] >= stop_price
        target_hit = bar["low"] <= target_price
    if stop_hit:
        return "stop", stop_price
    if target_hit:
        return "target", target_price
    return None, None
