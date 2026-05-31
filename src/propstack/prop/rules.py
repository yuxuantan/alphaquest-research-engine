from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PropRules:
    starting_balance: float = 50000
    daily_loss_limit: float = 1000
    trailing_drawdown: float = 2500
    max_contracts: int = 5
    max_best_day_profit_percentage: float = 0.4
    min_trading_days: int = 2
    payout_threshold: float = 1000
    profit_target_pct: float = 0.06
    drawdown_limit_pct: float = 0.03

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
