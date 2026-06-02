from __future__ import annotations

import pandas as pd

from propstack.backtest.fills import entry_price, exit_price, stop_target_hit
from propstack.backtest.metrics import calculate_metrics, daily_results
from propstack.backtest.risk import DailyRisk
from propstack.backtest.sizing import size_position
from propstack.strategy import ModularStrategy
from propstack.utils.progress import progress_bar
from propstack.utils.time import parse_time


class BacktestEngine:
    def __init__(self, config: dict, show_progress: bool = False):
        self.config = config
        self.strategy_config = dict(config.get("strategy", {}))
        if "strategy_name" not in self.strategy_config and config.get("strategy_name"):
            self.strategy_config["strategy_name"] = config["strategy_name"]
        self.core_config = config.get("core", {})
        self.show_progress = show_progress

    def run(self, data: pd.DataFrame) -> dict:
        df = data.sort_values("timestamp").reset_index(drop=True)
        strategy = ModularStrategy(self.strategy_config)
        entry_params = self.strategy_config.get("entry", {}).get("params", {})
        risk = DailyRisk({**self.core_config, **self.strategy_config, **entry_params})
        tick_size = float(self.core_config.get("tick_size", 0.25))
        tick_value = float(self.core_config.get("tick_value", 12.5))
        commission = float(self.core_config.get("commission_per_contract", 2.5))
        slippage_ticks = float(self.core_config.get("slippage_ticks", 1))
        flatten_time = parse_time(self.strategy_config.get("flatten_time", self.core_config.get("flatten_time", "14:55:00")))

        pending_signal = None
        position = None
        trades = []
        trade_id = 1
        progress = progress_bar(len(df), "bars", enabled=self.show_progress)

        for i, bar in df.iterrows():
            progress.update(i + 1)
            if pending_signal is not None and position is None and risk.allow_new_trade(bar["session_date"]):
                sig = pending_signal
                direction = sig.direction
                ep = entry_price(float(bar["open"]), direction, tick_size, slippage_ticks)
                stop = strategy.stop_price(sig, direction, tick_size, entry_price=ep)
                if stop is None:
                    pending_signal = None
                    continue
                risk_points = abs(ep - stop)
                sizing = size_position(self.core_config, risk_points, tick_size, tick_value)
                if sizing.contracts < 1:
                    pending_signal = None
                    continue
                target = strategy.target_price(ep, stop, direction, signal=sig)
                position = {
                    "trade_id": trade_id,
                    "strategy_name": strategy.name,
                    "session_date": bar["session_date"],
                    "direction": direction,
                    "level_type": sig.level_type,
                }
                if sig.report_fields:
                    position.update(sig.report_fields)
                else:
                    position.update(
                        {
                            "swept_level": sig.swept_level,
                            "sweep_timestamp": sig.sweep_timestamp,
                            "sweep_high": sig.sweep_high,
                            "sweep_low": sig.sweep_low,
                            "reclaim_timestamp": sig.reclaim_timestamp,
                        }
                    )
                position.update(
                    {
                        "entry_timestamp": bar["timestamp"],
                        "entry_price": ep,
                        "stop_price": stop,
                        "target_price": target,
                        "risk_points": risk_points,
                        "contracts": sizing.contracts,
                        "max_favorable_excursion": 0.0,
                        "max_adverse_excursion": 0.0,
                    }
                )
                position.update(sizing.report_fields())
                risk.record_entry(bar["session_date"])
                trade_id += 1
            pending_signal = None

            if position is not None:
                direction = position["direction"]
                if direction == "long":
                    mfe = max(0.0, float(bar["high"]) - position["entry_price"])
                    mae = max(0.0, position["entry_price"] - float(bar["low"]))
                else:
                    mfe = max(0.0, position["entry_price"] - float(bar["low"]))
                    mae = max(0.0, float(bar["high"]) - position["entry_price"])
                position["max_favorable_excursion"] = max(position["max_favorable_excursion"], mfe)
                position["max_adverse_excursion"] = max(position["max_adverse_excursion"], mae)

                reason, raw_exit = stop_target_hit(bar, direction, position["stop_price"], position["target_price"])
                if reason is None and bar["timestamp"].time() >= flatten_time:
                    reason, raw_exit = "eod_flatten", float(bar["close"])
                if reason is not None:
                    xp = exit_price(float(raw_exit), direction, tick_size, slippage_ticks)
                    point_pnl = xp - position["entry_price"] if direction == "long" else position["entry_price"] - xp
                    contracts = int(position["contracts"])
                    gross = point_pnl / tick_size * tick_value * contracts
                    total_commission = commission * contracts * 2
                    slippage_cost = slippage_ticks * tick_value * contracts * 2
                    net = gross - total_commission
                    r_mult = point_pnl / position["risk_points"] if position["risk_points"] else 0.0
                    trade = {
                        **position,
                        "exit_timestamp": bar["timestamp"],
                        "exit_price": xp,
                        "exit_reason": reason,
                        "gross_pnl": gross,
                        "net_pnl": net,
                        "r_multiple": r_mult,
                        "commission": total_commission,
                        "slippage_cost": slippage_cost,
                    }
                    trades.append(trade)
                    risk.record_exit(position["session_date"], net)
                    position = None
                    continue

            if position is None and risk.allow_new_trade(bar["session_date"]):
                signal = strategy.on_bar_close(bar, risk.trades_today(bar["session_date"]))
                if signal is not None:
                    pending_signal = signal

        trades_df = pd.DataFrame(trades)
        return {
            "trades": trades_df,
            "daily": daily_results(trades_df),
            "metrics": calculate_metrics(
                trades_df,
                initial_balance=float(self.core_config.get("initial_balance", 0)),
            ),
        }
