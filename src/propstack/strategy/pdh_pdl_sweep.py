from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry import Signal, build_entry_module
from propstack.strategy_modules.sl import build_sl_module
from propstack.strategy_modules.tp import build_tp_module


class PdhPdlSweepReclaim:
    def __init__(self, config: dict):
        self.config = _normalize_strategy_config(config)
        self.name = self.config.get("strategy_name", "pdh_pdl_sweep")
        self.entry = build_entry_module(self.config["entry"])
        self.tp = build_tp_module(self.config["tp"])
        self.sl = build_sl_module(self.config["sl"])

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        return self.entry.on_bar_close(bar, trades_today=trades_today)

    def stop_price(self, signal: Signal, direction: str, tick_size: float) -> float:
        return self.sl.price(signal, direction, tick_size)

    def target_price(self, entry_price: float, stop_price: float, direction: str) -> float:
        return self.tp.price(entry_price, stop_price, direction)


def _normalize_strategy_config(config: dict) -> dict:
    if "entry" in config and "tp" in config and "sl" in config:
        return config

    # Backward compatibility for older flat campaign/test configs.
    return {
        **config,
        "entry": {
            "module": "pdh_pdl_sweep_reclaim",
            "params": {
                "reclaim_window_bars": config.get("reclaim_window_bars", 3),
                "min_volume_ratio": config.get("min_volume_ratio", 0.0),
                "start_time": config.get("start_time", "08:30:00"),
                "end_time": config.get("end_time", "14:45:00"),
                "max_trades_per_day": config.get("max_trades_per_day", 999),
                "allow_long": config.get("allow_long", True),
                "allow_short": config.get("allow_short", True),
            },
        },
        "tp": {
            "module": "fixed_r",
            "params": {
                "target_r_multiple": config.get("target_r_multiple", 1.5),
            },
        },
        "sl": {
            "module": "sweep_extreme",
            "params": {
                "stop_offset_ticks": config.get("stop_offset_ticks", 1),
            },
        },
    }
