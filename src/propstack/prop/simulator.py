from __future__ import annotations

import math
import pandas as pd

from propstack.backtest.sizing import tick_value_from_core
from propstack.prop.rules import PropRules

REFERENCE_POSITION_SIZING_MODES = {"reference", "source", "source_trade", "source_trade_log"}
FIXED_POSITION_SIZING_MODES = {"fixed", "fixed_contracts"}
INITIAL_BALANCE_RISK_MODES = {
    "risk_percent_initial_balance",
    "initial_balance_risk",
    "risk_pct_initial_balance",
    "risk_percent_init_net_liq",
    "percent_initial_net_liq",
    "percent_init_net_liq",
}
CURRENT_NET_LIQ_RISK_MODES = {
    "risk_percent_net_liq",
    "net_liq_risk",
    "risk_pct_net_liq",
    "risk_percent_current_net_liq",
    "percent_current_net_liq",
    "current_net_liq_risk",
}
RISK_PERCENT_POSITION_SIZING_MODES = INITIAL_BALANCE_RISK_MODES | CURRENT_NET_LIQ_RISK_MODES


def simulate_prop_path(trades: pd.DataFrame, rules: PropRules, sizing_config: dict | None = None) -> dict:
    result, _ = _simulate_prop_path(trades, rules, sizing_config=sizing_config, collect_events=False)
    return result


def simulate_prop_path_with_events(
    trades: pd.DataFrame,
    rules: PropRules,
    sizing_config: dict | None = None,
) -> tuple[dict, list[dict]]:
    return _simulate_prop_path(trades, rules, sizing_config=sizing_config, collect_events=True)


def _simulate_prop_path(
    trades: pd.DataFrame,
    rules: PropRules,
    sizing_config: dict | None = None,
    collect_events: bool = False,
) -> tuple[dict, list[dict]]:
    if bool(getattr(rules, "account_lifecycle_enabled", False)):
        return _simulate_prop_account_lifecycle_path(
            trades,
            rules,
            sizing_config=sizing_config,
            collect_events=collect_events,
        )

    sizing_config = dict(sizing_config or {})
    sizing_config.setdefault("initial_net_liq", rules.starting_balance)
    balance = rules.starting_balance
    high = balance
    floor = high - rules.trailing_drawdown
    breached = False
    reason = ""
    daily_pnl = {}
    max_consec = cur = 0
    peak_equity = balance
    max_dd = 0.0
    profit_before_drawdown = False
    drawdown_before_profit = False
    profit_target_amount = getattr(rules, "profit_target_amount", None)
    drawdown_limit_amount = getattr(rules, "drawdown_limit_amount", None)
    profit_target = (
        rules.starting_balance + float(profit_target_amount)
        if profit_target_amount is not None
        else rules.starting_balance * (1 + getattr(rules, "profit_target_pct", 0.06))
    )
    drawdown_limit = (
        rules.starting_balance - float(drawdown_limit_amount)
        if drawdown_limit_amount is not None
        else rules.starting_balance * (1 - getattr(rules, "drawdown_limit_pct", 0.03))
    )
    payout_target = rules.starting_balance + rules.payout_threshold
    payout_eligible = False
    drawdown_before_payout = False
    events = []

    for _, trade in trades.iterrows():
        path_index = _trade_value(trade, "_path_index")
        source_trade_id = _trade_value(trade, "_source_trade_id", _trade_value(trade, "trade_id"))
        source_session_date = _trade_value(trade, "session_date")
        sim = _simulated_trade_values(trade, balance, sizing_config)
        if sim["sim_contracts"] < 1:
            if collect_events:
                events.append(
                    _event_row(
                        path_index,
                        source_trade_id,
                        source_session_date,
                        balance,
                        high,
                        floor,
                        max_dd,
                        drawdown_limit,
                        payout_target,
                        profit_target,
                        "position_size_skip",
                        reason,
                        sim_values=sim,
                    )
                )
            continue
        max_contracts_capped = False
        if int(sim["sim_contracts"]) > rules.max_contracts:
            sim = _cap_sim_contracts(sim, rules.max_contracts, sizing_config)
            max_contracts_capped = True
            if sim["sim_contracts"] < 1:
                if collect_events:
                    events.append(
                        _event_row(
                            path_index,
                            source_trade_id,
                            source_session_date,
                            balance,
                            high,
                            floor,
                            max_dd,
                            drawdown_limit,
                            payout_target,
                            profit_target,
                            "position_size_skip",
                            reason,
                            sim_values=sim,
                        )
                    )
                continue
        pnl = float(sim["sim_net_pnl"])
        balance += pnl
        daily_pnl[source_session_date] = daily_pnl.get(source_session_date, 0.0) + pnl
        high = max(high, balance)
        floor = max(floor, high - rules.trailing_drawdown)
        peak_equity = max(peak_equity, balance)
        max_dd = max(max_dd, peak_equity - balance)
        if pnl < 0:
            cur += 1
            max_consec = max(max_consec, cur)
        else:
            cur = 0
        event_names = ["trade"]
        if max_contracts_capped:
            event_names.append("max_contracts_capped")
        if balance <= floor:
            breached, reason = True, "trailing_drawdown"
            event_names.append("trailing_drawdown_breach")
            if collect_events:
                events.append(
                    _event_row(
                        path_index,
                        source_trade_id,
                        source_session_date,
                        balance,
                        high,
                        floor,
                        max_dd,
                        drawdown_limit,
                        payout_target,
                        profit_target,
                        "|".join(event_names),
                        reason,
                        sim_values=sim,
                    )
                )
            break
        if not profit_before_drawdown and not drawdown_before_profit:
            if balance >= profit_target:
                profit_before_drawdown = True
                event_names.append("profit_target_reached")
            elif balance <= drawdown_limit:
                drawdown_before_profit = True
                event_names.append("drawdown_limit_reached")
        if not payout_eligible and not drawdown_before_payout:
            if balance >= payout_target:
                payout_eligible = True
                event_names.append("payout_threshold_reached")
            elif balance <= drawdown_limit:
                drawdown_before_payout = True
                event_names.append("drawdown_limit_before_payout")
        if collect_events:
            events.append(
                _event_row(
                    path_index,
                    source_trade_id,
                    source_session_date,
                    balance,
                    high,
                    floor,
                    max_dd,
                    drawdown_limit,
                    payout_target,
                    profit_target,
                    "|".join(event_names),
                    reason,
                    sim_values=sim,
                )
            )

    daily = pd.Series(daily_pnl, dtype=float)
    worst_day = float(daily.min()) if len(daily) else 0.0
    best_day = float(daily.max()) if len(daily) else 0.0
    for session_date, pnl in daily.items():
        if pnl <= -rules.daily_loss_limit:
            breached, reason = True, "daily_loss_limit"
            if collect_events:
                events.append(
                    _event_row(
                        None,
                        None,
                        session_date,
                        balance,
                        high,
                        floor,
                        max_dd,
                        drawdown_limit,
                        payout_target,
                        profit_target,
                        "daily_loss_limit_breach",
                        reason,
                        daily_pnl=float(pnl),
                    )
                )
            break

    total_profit = balance - rules.starting_balance
    concentration = best_day / total_profit if total_profit > 0 else 0.0
    result = {
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
    return result, events


def _simulate_prop_account_lifecycle_path(
    trades: pd.DataFrame,
    rules: PropRules,
    sizing_config: dict | None = None,
    collect_events: bool = False,
) -> tuple[dict, list[dict]]:
    sizing_config = dict(sizing_config or {})
    sizing_config.setdefault("initial_net_liq", rules.starting_balance)
    events = []
    event_sequence = 0
    state = None
    day_pnls = []
    total_challenge_fees = 0.0
    gross_payouts = 0.0
    net_payouts = 0.0
    accounts_purchased = 0
    accounts_breached = 0
    accounts_terminated = 0
    challenge_passes = 0
    funded_accounts_started = 0
    payout_count = 0
    first_account_breached_before_challenge_pass = False
    last_breach_reason = ""
    max_consec = cur = 0
    max_dd = 0.0
    challenge_starting_balance = float(rules.starting_balance)
    funded_starting_balance = float(getattr(rules, "funded_starting_balance", rules.starting_balance))

    def trader_net_pnl() -> float:
        return net_payouts - total_challenge_fees

    def append_event(
        path_index,
        source_trade_id,
        source_session_date,
        event: str,
        breach_reason: str = "",
        daily_pnl=None,
        sim_values: dict | None = None,
        payout_request: float | None = None,
        payout_net: float | None = None,
    ) -> None:
        nonlocal event_sequence
        if not collect_events:
            return
        event_sequence += 1
        active = state or {}
        events.append(
            _event_row(
                path_index,
                source_trade_id,
                source_session_date,
                active.get("balance", funded_starting_balance),
                active.get("account_high", funded_starting_balance),
                active.get("floor", funded_starting_balance - float(rules.trailing_drawdown)),
                active.get("max_drawdown", max_dd),
                active.get("floor", funded_starting_balance - float(rules.trailing_drawdown)),
                active.get("next_payout_target_balance"),
                active.get("profit_target_balance"),
                event,
                breach_reason,
                daily_pnl=daily_pnl,
                sim_values=sim_values,
                event_sequence=event_sequence,
                account_number=active.get("account_number"),
                account_phase=active.get("phase"),
                trader_net_pnl=trader_net_pnl(),
                total_challenge_fees=total_challenge_fees,
                gross_payouts=gross_payouts,
                net_payouts=net_payouts,
                total_payout_count=payout_count,
                account_payout_count=active.get("account_payout_count"),
                funded_profit_days=active.get("funded_profit_days"),
                challenge_total_profit=active.get("challenge_total_profit"),
                challenge_largest_trade_profit=active.get("challenge_largest_trade_profit"),
                challenge_consistency_ratio=_challenge_consistency_ratio(active),
                payout_request=payout_request,
                payout_net=payout_net,
                account_breached=bool(breach_reason),
            )
        )

    def purchase_account(path_index, source_trade_id, source_session_date, reason: str) -> None:
        nonlocal state, accounts_purchased, total_challenge_fees
        accounts_purchased += 1
        total_challenge_fees += float(getattr(rules, "challenge_fee", 0.0))
        state = _new_challenge_account_state(accounts_purchased, rules)
        append_event(
            path_index,
            source_trade_id,
            source_session_date,
            f"account_purchased|{reason}",
        )

    def close_account_for_breach(
        path_index,
        source_trade_id,
        source_session_date,
        reason: str,
        sim_values: dict | None = None,
    ) -> None:
        nonlocal state, accounts_breached, first_account_breached_before_challenge_pass
        nonlocal last_breach_reason, max_dd
        if state is None:
            return
        accounts_breached += 1
        last_breach_reason = reason
        if challenge_passes == 0:
            first_account_breached_before_challenge_pass = True
        max_dd = max(max_dd, float(state.get("max_drawdown", 0.0)))
        append_event(
            path_index,
            source_trade_id,
            source_session_date,
            "account_breached",
            breach_reason=reason,
            daily_pnl=state.get("current_day_pnl"),
            sim_values=sim_values,
        )
        if state.get("current_session_date") is not None:
            day_pnls.append(float(state.get("current_day_pnl", 0.0)))
        state = None

    def start_funded_account(source_session_date) -> None:
        nonlocal state, funded_accounts_started
        if state is None:
            return
        funded_accounts_started += 1
        account_number = int(state["account_number"])
        state = _new_funded_account_state(account_number, rules)
        append_event(
            None,
            None,
            source_session_date,
            "funded_account_started_after_challenge_pass",
        )

    def finalize_current_day(next_session_date=None) -> None:
        nonlocal state, gross_payouts, net_payouts, payout_count, accounts_terminated, max_dd
        if state is None or state.get("current_session_date") is None:
            return
        session_date = state["current_session_date"]
        daily_pnl = float(state.get("current_day_pnl", 0.0))
        day_pnls.append(daily_pnl)
        _update_eod_trailing_floor(state, rules)
        event_names = ["eod_update"]
        payout_request = None
        payout_net = None
        if state.get("phase") == "funded":
            if daily_pnl >= float(getattr(rules, "funded_payout_min_profit_day", 150.0)):
                state["funded_profit_days"] += 1
                event_names.append("funded_profit_day")
            required_days = int(getattr(rules, "funded_payout_required_profit_days", 5))
            if state["funded_profit_days"] >= required_days:
                payout_request = _funded_payout_request(state, rules)
                if payout_request > 0:
                    payout_net = payout_request * float(getattr(rules, "funded_payout_profit_share", 0.90))
                    state["balance"] -= payout_request
                    state["account_payout_count"] += 1
                    state["funded_profit_days"] = 0
                    gross_payouts += payout_request
                    net_payouts += payout_net
                    payout_count += 1
                    state["max_drawdown"] = max(
                        float(state.get("max_drawdown", 0.0)),
                        float(state["account_high"]) - float(state["balance"]),
                    )
                    state["next_payout_target_balance"] = _next_payout_target_balance(state, rules)
                    max_dd = max(max_dd, float(state.get("max_drawdown", 0.0)))
                    event_names.append("funded_payout")
                    if state["account_payout_count"] >= int(getattr(rules, "max_payouts_per_account", 5)):
                        event_names.append("account_terminated_after_max_payouts")
        append_event(
            None,
            None,
            session_date,
            "|".join(event_names),
            daily_pnl=daily_pnl,
            payout_request=payout_request,
            payout_net=payout_net,
        )
        if state is not None and int(state.get("account_payout_count") or 0) >= int(
            getattr(rules, "max_payouts_per_account", 5)
        ):
            accounts_terminated += 1
            state = None
            return
        if state is not None:
            state["current_session_date"] = next_session_date
            state["current_day_pnl"] = 0.0

    for _, trade in trades.iterrows():
        path_index = _trade_value(trade, "_path_index")
        source_trade_id = _trade_value(trade, "_source_trade_id", _trade_value(trade, "trade_id"))
        source_session_date = _trade_value(trade, "session_date")
        if state is None:
            purchase_account(path_index, source_trade_id, source_session_date, "initial_or_replacement")
        if state is not None and state.get("current_session_date") is None:
            state["current_session_date"] = source_session_date
        elif state is not None and state.get("current_session_date") != source_session_date:
            finalize_current_day(next_session_date=source_session_date)
            if state is None:
                purchase_account(path_index, source_trade_id, source_session_date, "after_termination")
            if state is not None and state.get("current_session_date") is None:
                state["current_session_date"] = source_session_date

        sim = _simulated_trade_values(trade, float(state["balance"]), sizing_config)
        if sim["sim_contracts"] < 1:
            append_event(
                path_index,
                source_trade_id,
                source_session_date,
                "position_size_skip",
                sim_values=sim,
            )
            continue
        max_contracts_capped = False
        if int(sim["sim_contracts"]) > rules.max_contracts:
            sim = _cap_sim_contracts(sim, rules.max_contracts, sizing_config)
            max_contracts_capped = True
            if sim["sim_contracts"] < 1:
                append_event(
                    path_index,
                    source_trade_id,
                    source_session_date,
                    "position_size_skip",
                    sim_values=sim,
                )
                continue

        pnl = float(sim["sim_net_pnl"])
        state["balance"] += pnl
        state["current_day_pnl"] = float(state.get("current_day_pnl", 0.0)) + pnl
        state["account_high"] = max(float(state["account_high"]), float(state["balance"]))
        state["max_drawdown"] = max(
            float(state.get("max_drawdown", 0.0)),
            float(state["account_high"]) - float(state["balance"]),
        )
        max_dd = max(max_dd, float(state["max_drawdown"]))
        if pnl < 0:
            cur += 1
            max_consec = max(max_consec, cur)
        else:
            cur = 0

        event_names = ["trade"]
        if max_contracts_capped:
            event_names.append("max_contracts_capped")
        phase = state.get("phase")
        if phase == "challenge":
            state["challenge_largest_trade_profit"] = max(
                float(state.get("challenge_largest_trade_profit", 0.0)),
                pnl if pnl > 0 else 0.0,
            )
            state["challenge_total_profit"] = float(state["balance"]) - challenge_starting_balance
            if _challenge_is_passed(state, rules):
                challenge_passes += 1
                event_names.append("challenge_passed")
                append_event(
                    path_index,
                    source_trade_id,
                    source_session_date,
                    "|".join(event_names),
                    sim_values=sim,
                )
                if state.get("current_session_date") is not None:
                    day_pnls.append(float(state.get("current_day_pnl", 0.0)))
                start_funded_account(source_session_date)
                continue
            if float(state["balance"]) < float(state["floor"]):
                event_names.append("trailing_drawdown_breach")
                append_event(
                    path_index,
                    source_trade_id,
                    source_session_date,
                    "|".join(event_names),
                    breach_reason="trailing_drawdown",
                    sim_values=sim,
                )
                close_account_for_breach(
                    path_index,
                    source_trade_id,
                    source_session_date,
                    "trailing_drawdown",
                    sim_values=sim,
                )
                continue
        elif phase == "funded":
            if float(state["balance"]) < float(state["floor"]):
                event_names.append("trailing_drawdown_breach")
                append_event(
                    path_index,
                    source_trade_id,
                    source_session_date,
                    "|".join(event_names),
                    breach_reason="trailing_drawdown",
                    sim_values=sim,
                )
                close_account_for_breach(
                    path_index,
                    source_trade_id,
                    source_session_date,
                    "trailing_drawdown",
                    sim_values=sim,
                )
                continue

        append_event(
            path_index,
            source_trade_id,
            source_session_date,
            "|".join(event_names),
            sim_values=sim,
        )

    finalize_current_day()
    account_ending_balance = None if state is None else float(state["balance"])
    final_phase = "" if state is None else str(state["phase"])
    worst_day = min(day_pnls) if day_pnls else 0.0
    best_day = max(day_pnls) if day_pnls else 0.0
    concentration_base = sum(pnl for pnl in day_pnls if pnl > 0)
    concentration = best_day / concentration_base if concentration_base > 0 else 0.0
    net_pnl = trader_net_pnl()
    result = {
        "ending_balance": funded_starting_balance + net_pnl,
        "net_pnl": net_pnl,
        "trader_net_pnl": net_pnl,
        "account_ending_balance": account_ending_balance,
        "final_account_phase": final_phase,
        "max_drawdown": max_dd,
        "worst_day": float(worst_day),
        "best_day": float(best_day),
        "best_day_concentration": float(concentration),
        "max_consecutive_losses": max_consec,
        "account_breached": accounts_breached > 0,
        "breach_reason": last_breach_reason,
        "payout_eligible": payout_count > 0,
        "profit_before_drawdown": challenge_passes > 0,
        "drawdown_before_profit": first_account_breached_before_challenge_pass,
        "accounts_purchased": accounts_purchased,
        "accounts_breached": accounts_breached,
        "accounts_terminated": accounts_terminated,
        "challenge_passes": challenge_passes,
        "funded_accounts_started": funded_accounts_started,
        "payout_count": payout_count,
        "gross_payouts": gross_payouts,
        "net_payouts": net_payouts,
        "total_challenge_fees": total_challenge_fees,
    }
    return result, events


def _new_challenge_account_state(account_number: int, rules: PropRules) -> dict:
    balance = float(rules.starting_balance)
    floor = balance - float(rules.trailing_drawdown)
    return {
        "account_number": int(account_number),
        "phase": "challenge",
        "balance": balance,
        "account_high": balance,
        "eod_high": balance,
        "floor": floor,
        "max_drawdown": 0.0,
        "current_session_date": None,
        "current_day_pnl": 0.0,
        "challenge_total_profit": 0.0,
        "challenge_largest_trade_profit": 0.0,
        "profit_target_balance": balance + float(getattr(rules, "challenge_profit_target_amount", 3000.0)),
        "next_payout_target_balance": None,
        "funded_profit_days": None,
        "account_payout_count": None,
    }


def _new_funded_account_state(account_number: int, rules: PropRules) -> dict:
    balance = float(getattr(rules, "funded_starting_balance", rules.starting_balance))
    floor = getattr(rules, "funded_initial_drawdown_floor", None)
    if floor is None:
        floor = balance - float(rules.trailing_drawdown)
    return {
        "account_number": int(account_number),
        "phase": "funded",
        "balance": balance,
        "account_high": balance,
        "eod_high": balance,
        "floor": float(floor),
        "max_drawdown": 0.0,
        "current_session_date": None,
        "current_day_pnl": 0.0,
        "challenge_total_profit": None,
        "challenge_largest_trade_profit": None,
        "profit_target_balance": None,
        "next_payout_target_balance": balance + float(getattr(rules, "funded_payout_min_profit_day", 150.0)),
        "funded_profit_days": 0,
        "account_payout_count": 0,
    }


def _update_eod_trailing_floor(state: dict, rules: PropRules) -> None:
    state["eod_high"] = max(float(state.get("eod_high", state["balance"])), float(state["balance"]))
    floor_candidate = float(state["eod_high"]) - float(rules.trailing_drawdown)
    lock_balance = getattr(rules, "trailing_drawdown_lock_balance", None)
    locked_floor = getattr(rules, "trailing_drawdown_locked_floor", None)
    if lock_balance is not None and locked_floor is not None and float(state["eod_high"]) >= float(lock_balance):
        floor_candidate = float(locked_floor)
    elif locked_floor is not None:
        floor_candidate = min(floor_candidate, float(locked_floor))
    state["floor"] = max(float(state["floor"]), floor_candidate)


def _challenge_is_passed(state: dict, rules: PropRules) -> bool:
    total_profit = float(state.get("challenge_total_profit", 0.0))
    if total_profit < float(getattr(rules, "challenge_profit_target_amount", 3000.0)):
        return False
    ratio = _challenge_consistency_ratio(state)
    return ratio <= float(getattr(rules, "challenge_consistency_limit", 0.50))


def _challenge_consistency_ratio(state: dict) -> float | None:
    total_profit = state.get("challenge_total_profit")
    largest_profit = state.get("challenge_largest_trade_profit")
    if total_profit is None or largest_profit is None or float(total_profit) <= 0:
        return None
    return float(largest_profit) / float(total_profit)


def _funded_payout_request(state: dict, rules: PropRules) -> float:
    funded_start = float(getattr(rules, "funded_starting_balance", rules.starting_balance))
    profit = float(state["balance"]) - funded_start
    if profit <= 0:
        return 0.0
    request = profit * float(getattr(rules, "funded_payout_profit_fraction", 0.50))
    return min(request, float(getattr(rules, "funded_payout_max_amount", 2000.0)))


def _next_payout_target_balance(state: dict, rules: PropRules) -> float:
    funded_start = float(getattr(rules, "funded_starting_balance", rules.starting_balance))
    return funded_start + (2.0 * float(getattr(rules, "funded_payout_min_profit_day", 150.0)))


def _event_row(
    path_index,
    source_trade_id,
    source_session_date,
    balance: float,
    high: float,
    trailing_floor: float,
    max_drawdown: float,
    drawdown_limit_balance: float,
    payout_target_balance: float,
    profit_target_balance: float,
    event: str,
    breach_reason: str,
    daily_pnl=None,
    sim_values: dict | None = None,
    **extra,
) -> dict:
    sim_values = sim_values or {}
    row = {
        "path_index": path_index,
        "source_trade_id": source_trade_id,
        "source_session_date": source_session_date,
        "source_contracts": sim_values.get("source_contracts"),
        "sim_contracts": sim_values.get("sim_contracts"),
        "source_net_pnl": sim_values.get("source_net_pnl"),
        "sim_net_pnl": sim_values.get("sim_net_pnl"),
        "position_sizing_mode": sim_values.get("position_sizing_mode"),
        "position_sizing_net_liq": sim_values.get("position_sizing_net_liq"),
        "target_risk_amount": sim_values.get("target_risk_amount"),
        "dollar_risk_per_contract": sim_values.get("dollar_risk_per_contract"),
        "unrounded_contracts": sim_values.get("unrounded_contracts"),
        "planned_dollar_risk": sim_values.get("planned_dollar_risk"),
        "balance": balance,
        "account_high": high,
        "trailing_floor": trailing_floor,
        "max_drawdown": max_drawdown,
        "drawdown_limit_balance": drawdown_limit_balance,
        "payout_target_balance": payout_target_balance,
        "profit_target_balance": profit_target_balance,
        "event": event,
        "breach_reason": breach_reason,
        "daily_pnl": daily_pnl,
    }
    row.update(extra)
    return row


def _trade_value(trade, key: str, default=None):
    value = trade.get(key, default)
    if hasattr(value, "item"):
        value = value.item()
    if pd.isna(value):
        return default
    return value


def _simulated_trade_values(trade, net_liq: float, sizing_config: dict) -> dict:
    source_contracts = int(_trade_value(trade, "contracts", 1) or 1)
    source_net_pnl = float(
        _trade_value(trade, "_source_net_pnl", _trade_value(trade, "net_pnl", 0.0)) or 0.0
    )
    adverse = float(sizing_config.get("adverse_slippage_per_trade", 0.0))
    position_sizing_mode = _normalize_source_position_sizing_mode(
        _trade_value(trade, "position_sizing_mode", "fixed_contracts")
    )
    monte_carlo_sizing = _monte_carlo_position_sizing(sizing_config)
    monte_carlo_mode = _normalize_monte_carlo_position_sizing_mode(
        monte_carlo_sizing.get("mode", "reference")
    )

    if monte_carlo_mode in FIXED_POSITION_SIZING_MODES:
        size = _fixed_path_position_size(monte_carlo_sizing)
        return _scaled_trade_values(
            source_contracts,
            source_net_pnl,
            adverse,
            size,
            "fixed_contracts",
            None,
        )

    if monte_carlo_mode in RISK_PERCENT_POSITION_SIZING_MODES:
        risk_base = _risk_base_for_mode(monte_carlo_mode, net_liq, sizing_config)
        size = _path_position_size(
            trade,
            risk_base,
            sizing_config,
            monte_carlo_sizing,
            "monte_carlo.position_sizing",
        )
        return _scaled_trade_values(
            source_contracts,
            source_net_pnl,
            adverse,
            size,
            _canonical_risk_percent_mode(monte_carlo_mode),
            risk_base,
        )

    if _should_resize_trade(position_sizing_mode, sizing_config):
        risk_base = float(net_liq)
        size = _path_position_size(
            trade,
            risk_base,
            sizing_config,
            _core_position_sizing(sizing_config),
            "core.position_sizing",
        )
        return _scaled_trade_values(
            source_contracts,
            source_net_pnl,
            adverse,
            size,
            "risk_percent_net_liq",
            risk_base,
        )

    return {
        "source_contracts": source_contracts,
        "sim_contracts": source_contracts,
        "source_net_pnl": source_net_pnl,
        "sim_net_pnl": source_net_pnl - adverse,
        "position_sizing_mode": position_sizing_mode,
        "position_sizing_net_liq": None,
        "target_risk_amount": None,
        "dollar_risk_per_contract": _trade_value(trade, "dollar_risk_per_contract"),
        "unrounded_contracts": None,
        "planned_dollar_risk": None,
    }


def _scaled_trade_values(
    source_contracts: int,
    source_net_pnl: float,
    adverse: float,
    size: dict,
    position_sizing_mode: str,
    position_sizing_net_liq: float | None,
) -> dict:
    sim_contracts = int(size["contracts"])
    if source_contracts <= 0 or sim_contracts <= 0:
        sim_net_pnl = 0.0
    else:
        sim_net_pnl = (source_net_pnl / source_contracts) * sim_contracts - adverse
    return {
        "source_contracts": source_contracts,
        "sim_contracts": sim_contracts,
        "source_net_pnl": source_net_pnl,
        "sim_net_pnl": sim_net_pnl,
        "position_sizing_mode": position_sizing_mode,
        "position_sizing_net_liq": (
            None if position_sizing_net_liq is None else float(position_sizing_net_liq)
        ),
        "target_risk_amount": size.get("target_risk_amount"),
        "dollar_risk_per_contract": size.get("dollar_risk_per_contract"),
        "unrounded_contracts": size.get("unrounded_contracts"),
        "planned_dollar_risk": size.get("planned_dollar_risk"),
    }


def _cap_sim_contracts(sim_values: dict, max_contracts: int, sizing_config: dict) -> dict:
    capped_contracts = max(0, int(max_contracts))
    out = dict(sim_values)
    out["sim_contracts"] = capped_contracts

    source_contracts = int(out.get("source_contracts") or 0)
    source_net_pnl = _float_or_default(out.get("source_net_pnl"), 0.0)
    adverse = float(sizing_config.get("adverse_slippage_per_trade", 0.0))
    if source_contracts <= 0 or capped_contracts <= 0:
        out["sim_net_pnl"] = 0.0
    else:
        out["sim_net_pnl"] = (source_net_pnl / source_contracts) * capped_contracts - adverse

    dollar_risk_per_contract = out.get("dollar_risk_per_contract")
    if dollar_risk_per_contract is not None and not pd.isna(dollar_risk_per_contract):
        out["planned_dollar_risk"] = float(dollar_risk_per_contract) * capped_contracts
    return out


def _float_or_default(value, default: float) -> float:
    if value is None or pd.isna(value):
        return default
    return float(value)


def _should_resize_trade(position_sizing_mode: str, sizing_config: dict) -> bool:
    core_mode = _normalize_source_position_sizing_mode(
        _core_position_sizing(sizing_config).get("mode", "fixed_contracts")
    )
    return (
        position_sizing_mode in RISK_PERCENT_POSITION_SIZING_MODES
        and core_mode in RISK_PERCENT_POSITION_SIZING_MODES
    )


def _path_position_size(
    trade,
    risk_base: float,
    sizing_config: dict,
    sizing: dict,
    config_name: str,
) -> dict:
    dollar_risk_per_contract = _dollar_risk_per_contract_from_trade(
        trade, sizing_config, config_name
    )
    if dollar_risk_per_contract <= 0:
        raise ValueError("Risk-percent Monte Carlo resizing requires risk_points or dollar_risk_per_contract.")
    risk_pct = _risk_pct_from_sizing(sizing, sizing_config, config_name)
    target_risk_amount = float(risk_base) * risk_pct if risk_base > 0 else 0.0
    unrounded = target_risk_amount / dollar_risk_per_contract if dollar_risk_per_contract else 0.0
    contracts = _round_contracts(
        unrounded,
        _rounding_from_sizing(sizing, sizing_config, config_name),
        config_name,
    )
    max_contracts = _max_contracts_from_sizing(sizing, sizing_config)
    if max_contracts is not None:
        contracts = min(contracts, max_contracts)
    min_contracts = _min_contracts_from_sizing(sizing, sizing_config)
    if contracts < min_contracts:
        contracts = 0
    return {
        "contracts": contracts,
        "target_risk_amount": target_risk_amount,
        "dollar_risk_per_contract": dollar_risk_per_contract,
        "unrounded_contracts": unrounded,
        "planned_dollar_risk": dollar_risk_per_contract * contracts,
    }


def _fixed_path_position_size(sizing: dict) -> dict:
    contracts = sizing.get("contracts")
    if contracts is None:
        raise ValueError("monte_carlo.position_sizing.contracts is required for fixed_contracts mode.")
    contracts = int(contracts)
    if contracts < 1:
        raise ValueError("monte_carlo.position_sizing.contracts must be at least 1.")
    return {
        "contracts": contracts,
        "target_risk_amount": None,
        "dollar_risk_per_contract": None,
        "unrounded_contracts": None,
        "planned_dollar_risk": None,
    }


def _dollar_risk_per_contract_from_trade(trade, sizing_config: dict, config_name: str) -> float:
    risk_points = _trade_value(trade, "risk_points")
    if risk_points is not None:
        core = sizing_config.get("core") or {}
        risk = float(risk_points)
        tick_size = float(core.get("tick_size", 0.25))
        tick_value = tick_value_from_core(core, tick_size)
        if risk <= 0:
            raise ValueError("risk_points must be greater than 0 for risk-percent Monte Carlo position sizing.")
        return risk / tick_size * tick_value
    dollar_risk_per_contract = float(_trade_value(trade, "dollar_risk_per_contract", 0.0) or 0.0)
    if dollar_risk_per_contract <= 0:
        raise ValueError(f"{config_name} risk-percent mode requires risk_points or dollar_risk_per_contract.")
    return dollar_risk_per_contract


def _risk_pct_from_sizing(sizing: dict, sizing_config: dict, config_name: str) -> float:
    fallback = _core_position_sizing(sizing_config)
    for source in (sizing, fallback):
        if "risk_pct" in source:
            risk_pct = float(source["risk_pct"])
            break
        if "risk_fraction" in source:
            risk_pct = float(source["risk_fraction"])
            break
        if "risk_percent" in source:
            risk_pct = float(source["risk_percent"]) / 100.0
            break
    else:
        risk_pct = 0.01
    if risk_pct <= 0:
        raise ValueError(f"{config_name} risk percentage must be greater than 0.")
    return risk_pct


def _rounding_from_sizing(sizing: dict, sizing_config: dict, config_name: str) -> str:
    fallback = _core_position_sizing(sizing_config)
    rounding = str(sizing.get("rounding", fallback.get("rounding", "floor"))).lower()
    if rounding not in {"floor", "nearest", "ceil"}:
        raise ValueError(f"{config_name}.rounding must be one of: floor, nearest, ceil.")
    return rounding


def _min_contracts_from_sizing(sizing: dict, sizing_config: dict) -> int:
    fallback = _core_position_sizing(sizing_config)
    return int(sizing.get("min_contracts", fallback.get("min_contracts", 1)))


def _max_contracts_from_sizing(sizing: dict, sizing_config: dict) -> int | None:
    fallback = _core_position_sizing(sizing_config)
    max_contracts = sizing.get("max_contracts", fallback.get("max_contracts"))
    return None if max_contracts is None else int(max_contracts)


def _risk_base_for_mode(mode: str, net_liq: float, sizing_config: dict) -> float:
    if mode in INITIAL_BALANCE_RISK_MODES:
        return float(sizing_config.get("initial_net_liq", net_liq))
    if mode in CURRENT_NET_LIQ_RISK_MODES:
        return float(net_liq)
    raise ValueError(f"Unsupported risk-percent position sizing mode: {mode}")


def _core_position_sizing(sizing_config: dict) -> dict:
    core = sizing_config.get("core") or {}
    sizing = core.get("position_sizing") or {}
    if isinstance(sizing, str):
        return {"mode": sizing}
    if sizing is None:
        return {}
    if not isinstance(sizing, dict):
        raise ValueError("core.position_sizing must be a mapping or mode string.")
    return dict(sizing)


def _monte_carlo_position_sizing(sizing_config: dict) -> dict:
    sizing = sizing_config.get("position_sizing") or {"mode": "reference"}
    if isinstance(sizing, str):
        sizing = {"mode": sizing}
    if sizing is None:
        sizing = {"mode": "reference"}
    if not isinstance(sizing, dict):
        raise ValueError("monte_carlo.position_sizing must be a mapping or mode string.")
    return dict(sizing)


def _normalize_monte_carlo_position_sizing_mode(mode) -> str:
    normalized = str(mode).strip().lower()
    if normalized in REFERENCE_POSITION_SIZING_MODES:
        return "reference"
    if normalized in FIXED_POSITION_SIZING_MODES:
        return "fixed_contracts"
    if normalized in INITIAL_BALANCE_RISK_MODES:
        return "risk_percent_initial_balance"
    if normalized in CURRENT_NET_LIQ_RISK_MODES:
        return "risk_percent_net_liq"
    raise ValueError(
        "monte_carlo.position_sizing.mode must be one of: "
        "reference, fixed_contracts, risk_percent_net_liq, risk_percent_initial_balance."
    )


def _normalize_source_position_sizing_mode(mode) -> str:
    normalized = str(mode).strip().lower()
    if normalized in FIXED_POSITION_SIZING_MODES:
        return "fixed_contracts"
    if normalized in INITIAL_BALANCE_RISK_MODES:
        return "risk_percent_initial_balance"
    if normalized in CURRENT_NET_LIQ_RISK_MODES:
        return "risk_percent_net_liq"
    return normalized


def _canonical_risk_percent_mode(mode: str) -> str:
    if mode in INITIAL_BALANCE_RISK_MODES:
        return "risk_percent_initial_balance"
    if mode in CURRENT_NET_LIQ_RISK_MODES:
        return "risk_percent_net_liq"
    raise ValueError(f"Unsupported risk-percent position sizing mode: {mode}")


def _round_contracts(unrounded: float, rounding: str, config_name: str) -> int:
    if rounding == "floor":
        return math.floor(unrounded)
    if rounding == "ceil":
        return math.ceil(unrounded)
    if rounding == "nearest":
        return math.floor(unrounded + 0.5)
    raise ValueError(f"{config_name}.rounding must be one of: floor, nearest, ceil.")
