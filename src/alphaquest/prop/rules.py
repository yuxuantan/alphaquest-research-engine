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
    profit_target_amount: float | None = None
    drawdown_limit_amount: float | None = None
    account_lifecycle_enabled: bool = False
    challenge_fee: float = 98.0
    challenge_profit_target_amount: float = 3000.0
    challenge_consistency_limit: float = 0.50
    trailing_drawdown_lock_balance: float | None = 52100.0
    trailing_drawdown_locked_floor: float | None = 50100.0
    funded_starting_balance: float = 50000.0
    funded_initial_drawdown_floor: float | None = 48000.0
    funded_payout_min_profit_day: float = 150.0
    funded_payout_required_profit_days: int = 5
    funded_payout_profit_fraction: float = 0.50
    funded_payout_profit_share: float = 0.90
    funded_payout_max_amount: float = 2000.0
    max_payouts_per_account: int = 5

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
