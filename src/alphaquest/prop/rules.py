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


CHALLENGE_PASS_RULE_FIELDS = frozenset(
    {
        "challenge_profit_target_amount",
        "challenge_consistency_limit",
        "max_best_day_profit_percentage",
        "min_trading_days",
    }
)

# This registry makes it testable that a certified PropRules field is not merely
# serialized into a profile while remaining dead in every simulator lane.
PROP_RULE_EXECUTION_COVERAGE = {
    "starting_balance": "all_account_initialization",
    "daily_loss_limit": "all_path_daily_breach",
    "trailing_drawdown": "all_path_drawdown",
    "max_contracts": "all_path_position_cap",
    "max_best_day_profit_percentage": "lifecycle_challenge_pass",
    "min_trading_days": "lifecycle_challenge_pass",
    "payout_threshold": "legacy_path_payout_eligibility",
    "profit_target_pct": "legacy_path_profit_target",
    "drawdown_limit_pct": "legacy_path_drawdown_limit",
    "profit_target_amount": "legacy_path_profit_target",
    "drawdown_limit_amount": "legacy_path_drawdown_limit",
    "account_lifecycle_enabled": "lane_selection",
    "challenge_fee": "lifecycle_external_pnl",
    "challenge_profit_target_amount": "lifecycle_challenge_pass",
    "challenge_consistency_limit": "lifecycle_challenge_pass",
    "trailing_drawdown_lock_balance": "lifecycle_eod_drawdown",
    "trailing_drawdown_locked_floor": "lifecycle_eod_drawdown",
    "funded_starting_balance": "lifecycle_funded_initialization",
    "funded_initial_drawdown_floor": "lifecycle_funded_initialization",
    "funded_payout_min_profit_day": "lifecycle_payout_eligibility",
    "funded_payout_required_profit_days": "lifecycle_payout_eligibility",
    "funded_payout_profit_fraction": "lifecycle_payout_amount",
    "funded_payout_profit_share": "lifecycle_external_pnl",
    "funded_payout_max_amount": "lifecycle_payout_amount",
    "max_payouts_per_account": "lifecycle_account_termination",
}

if set(PROP_RULE_EXECUTION_COVERAGE) != set(PropRules.__dataclass_fields__):
    raise RuntimeError("PropRules execution coverage must classify every executable rule field")
