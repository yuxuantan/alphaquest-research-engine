"""Certified, fully specified prop-simulation profiles for Studio campaigns."""

from __future__ import annotations

import hashlib
import json
from typing import Any


PROFILE_SCHEMA = "alphaquest.prop-profile/v1"
DEFAULT_PROP_PROFILE = "configured_local_profile"

_ALIASES = {
    "reviewed_local_profile": DEFAULT_PROP_PROFILE,
    "synthetic_tutorial_non_promotable": DEFAULT_PROP_PROFILE,
}

_CATALOG: dict[str, dict[str, Any]] = {
    DEFAULT_PROP_PROFILE: {
        "profile_id": DEFAULT_PROP_PROFILE,
        "name": "AlphaQuest local evaluation v1",
        "description": (
            "Vendor-neutral local research simulation with a 6% challenge target, "
            "4% trailing drawdown and fully declared payout lifecycle rules."
        ),
        "novice_visible": True,
        "account_lifecycle_enabled": True,
        "challenge_fee": 98.0,
        "challenge_profit_target_fraction": 0.06,
        "challenge_consistency_limit": 0.50,
        "drawdown_limit_fraction": 0.04,
        "max_best_day_profit_percentage": 0.40,
        "min_trading_days": 2,
        "funded_payout_min_profit_day": 150.0,
        "funded_payout_required_profit_days": 5,
        "funded_payout_profit_fraction": 0.50,
        "funded_payout_profit_share": 0.90,
        "funded_payout_max_amount": 2000.0,
        "max_payouts_per_account": 5,
    }
}


def list_prop_profiles(*, novice_only: bool = True) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for profile in _CATALOG.values():
        if novice_only and not profile.get("novice_visible"):
            continue
        rows.append(
            {
                "profile_id": profile["profile_id"],
                "name": profile["name"],
                "description": profile["description"],
                "challenge_profit_target_pct": 100 * profile["challenge_profit_target_fraction"],
                "drawdown_limit_pct": 100 * profile["drawdown_limit_fraction"],
                "challenge_consistency_limit_pct": 100 * profile["challenge_consistency_limit"],
                "minimum_trading_days": profile["min_trading_days"],
                "account_lifecycle_enabled": profile["account_lifecycle_enabled"],
            }
        )
    return rows


def resolve_prop_profile(
    profile_id: str,
    *,
    starting_balance: float,
    max_contracts: int,
    force_flatten_time: str,
) -> dict[str, Any]:
    canonical = _ALIASES.get(profile_id, profile_id)
    profile = _CATALOG.get(canonical)
    if profile is None:
        raise ValueError(
            f"unknown or uncertified prop profile: {profile_id}; select a governed Studio catalog entry"
        )
    balance = float(starting_balance)
    contracts = int(max_contracts)
    if balance <= 0 or contracts < 1:
        raise ValueError("prop-profile balance and contract count must be positive")
    drawdown = balance * float(profile["drawdown_limit_fraction"])
    target = balance * float(profile["challenge_profit_target_fraction"])
    lock_buffer = min(100.0, max(1.0, drawdown * 0.05))
    rules = {
        "schema": PROFILE_SCHEMA,
        "profile": canonical,
        "profile_fully_specified": True,
        "starting_balance": balance,
        "daily_loss_limit": drawdown,
        "trailing_drawdown": drawdown,
        "max_contracts": contracts,
        "max_best_day_profit_percentage": float(profile["max_best_day_profit_percentage"]),
        "min_trading_days": int(profile["min_trading_days"]),
        "payout_threshold": max(1000.0, target / 3.0),
        "profit_target_pct": float(profile["challenge_profit_target_fraction"]),
        "drawdown_limit_pct": float(profile["drawdown_limit_fraction"]),
        "profit_target_amount": target,
        "drawdown_limit_amount": drawdown,
        "account_lifecycle_enabled": bool(profile["account_lifecycle_enabled"]),
        "challenge_fee": float(profile["challenge_fee"]),
        "challenge_profit_target_amount": target,
        "challenge_consistency_limit": float(profile["challenge_consistency_limit"]),
        "trailing_drawdown_lock_balance": balance + drawdown + lock_buffer,
        "trailing_drawdown_locked_floor": balance + lock_buffer,
        "funded_starting_balance": balance,
        "funded_initial_drawdown_floor": balance - drawdown,
        "funded_payout_min_profit_day": float(profile["funded_payout_min_profit_day"]),
        "funded_payout_required_profit_days": int(profile["funded_payout_required_profit_days"]),
        "funded_payout_profit_fraction": float(profile["funded_payout_profit_fraction"]),
        "funded_payout_profit_share": float(profile["funded_payout_profit_share"]),
        "funded_payout_max_amount": float(profile["funded_payout_max_amount"]),
        "max_payouts_per_account": int(profile["max_payouts_per_account"]),
        "no_overnight_positions": True,
        "force_flatten_time": force_flatten_time,
    }
    rules["profile_sha256"] = hashlib.sha256(
        json.dumps(rules, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return rules


__all__ = ["DEFAULT_PROP_PROFILE", "PROFILE_SCHEMA", "list_prop_profiles", "resolve_prop_profile"]
