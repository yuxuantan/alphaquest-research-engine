from __future__ import annotations

import pandas as pd

from propstack.prop.rules import PropRules


def simulate_prop_path(trades: pd.DataFrame, rules: PropRules) -> dict:
    balance = rules.starting_balance
    high = balance
    floor = high - rules.trailing_drawdown
    breached = False
    reason = ""
    daily = trades.groupby("session_date")["net_pnl"].sum() if not trades.empty else pd.Series(dtype=float)
    worst_day = float(daily.min()) if len(daily) else 0.0
    best_day = float(daily.max()) if len(daily) else 0.0
    max_consec = cur = 0
    peak_equity = balance
    max_dd = 0.0
    profit_before_drawdown = False
    drawdown_before_profit = False
    profit_target = rules.starting_balance * (1 + getattr(rules, "profit_target_pct", 0.06))
    drawdown_limit = rules.starting_balance * (1 - getattr(rules, "drawdown_limit_pct", 0.03))
    payout_target = rules.starting_balance + rules.payout_threshold
    payout_eligible = False
    drawdown_before_payout = False

    for _, trade in trades.iterrows():
        if int(trade.get("contracts", 1)) > rules.max_contracts:
            breached, reason = True, "max_contracts"
            break
        pnl = float(trade["net_pnl"])
        balance += pnl
        high = max(high, balance)
        floor = max(floor, high - rules.trailing_drawdown)
        peak_equity = max(peak_equity, balance)
        max_dd = max(max_dd, peak_equity - balance)
        if pnl < 0:
            cur += 1
            max_consec = max(max_consec, cur)
        else:
            cur = 0
        if balance <= floor:
            breached, reason = True, "trailing_drawdown"
            break
        if not profit_before_drawdown and not drawdown_before_profit:
            if balance >= profit_target:
                profit_before_drawdown = True
            elif balance <= drawdown_limit:
                drawdown_before_profit = True
        if not payout_eligible and not drawdown_before_payout:
            if balance >= payout_target:
                payout_eligible = True
            elif balance <= drawdown_limit:
                drawdown_before_payout = True

    for _, pnl in daily.items():
        if pnl <= -rules.daily_loss_limit:
            breached, reason = True, "daily_loss_limit"
            break

    total_profit = balance - rules.starting_balance
    concentration = best_day / total_profit if total_profit > 0 else 0.0
    return {
        "ending_balance": balance,
        "net_pnl": total_profit,
        "max_drawdown": max_dd,
        "worst_day": worst_day,
        "best_day": best_day,
        "best_day_concentration": concentration,
        "max_consecutive_losses": max_consec,
        "account_breached": breached,
        "breach_reason": reason,
        "payout_eligible": payout_eligible,
        "profit_before_drawdown": profit_before_drawdown,
        "drawdown_before_profit": drawdown_before_profit,
    }
