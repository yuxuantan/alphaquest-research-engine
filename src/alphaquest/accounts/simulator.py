from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from alphaquest.accounts.models import (
    AccountAssessmentCostsV1,
    AccountRuleProfileV1,
    ScalingTierV1,
)


@dataclass(frozen=True)
class AccountPathEvaluation:
    summary: dict[str, Any]
    events: pd.DataFrame
    daily: pd.DataFrame


def evaluate_account_trade_path(
    trades: pd.DataFrame,
    profile: AccountRuleProfileV1,
    *,
    costs: AccountAssessmentCostsV1 | None = None,
    manual_attestations: Iterable[str] = (),
    evaluation_start: date | str | None = None,
    evaluation_end: date | str | None = None,
    source_evidence_session_count: int | None = None,
) -> AccountPathEvaluation:
    """Replay one frozen trade path through one account-phase contract.

    EOD accounts are enforced against intratrade equity.  The function therefore
    refuses to invent compliance when the trade log lacks either an absolute
    ``intraday_min_equity``, ``intratrade_min_pnl``/``mae_currency``, or a
    point excursion plus point value.
    """

    normalized, issues = _normalize_trades(trades)
    rules = profile.rules
    provided_attestations = {str(item).strip() for item in manual_attestations if str(item).strip()}
    missing_attestations = sorted(set(rules.manual_attestations_required) - provided_attestations)
    if missing_attestations:
        issues.append("missing manual attestations: " + ", ".join(missing_attestations))
    cost_required = (
        rules.acquisition.evaluation_price_mode == "assessment_input_required"
        or rules.acquisition.activation_fee_mode == "assessment_input_required"
    )
    if cost_required and costs is None:
        issues.append("timestamped checkout evaluation and activation costs are required")

    if normalized.empty:
        summary = _empty_summary(profile, issues or ["no trades are available"])
        return AccountPathEvaluation(summary, pd.DataFrame(), pd.DataFrame())

    if profile.identity.account_kind in {"prop_challenge", "prop_funded"} and rules.intraday_equity_required:
        missing_rows = [
            int(index)
            for index, row in normalized.iterrows()
            if _intratrade_min_equity(row, profile.identity.nominal_balance) is None
        ]
        if missing_rows:
            issues.append(
                "intraday equity cannot be reconstructed for "
                f"{len(missing_rows)} trades; supply equity marks, mae_currency, or point excursion plus point_value"
            )
    if not rules.overnight_positions_allowed:
        close_unknown = [
            int(index)
            for index, row in normalized.iterrows()
            if _position_close_compliant(row, profile) is None
        ]
        if close_unknown:
            issues.append(
                "position-close compliance cannot be established for "
                f"{len(close_unknown)} trades; supply exit_timestamp or forced_flatten_compliant"
            )

    start = _coerce_date(evaluation_start) or normalized["session_date"].min()
    end = _coerce_date(evaluation_end) or normalized["session_date"].max()
    if end < start:
        issues.append("evaluation_end precedes evaluation_start")

    if issues:
        summary = _empty_summary(profile, issues)
        summary["source_trade_count"] = int(len(normalized))
        summary["source_session_count"] = int(normalized["session_date"].nunique())
        return AccountPathEvaluation(summary, pd.DataFrame(), pd.DataFrame())

    starting_balance = float(profile.identity.nominal_balance)
    balance = starting_balance
    peak_equity = balance
    max_drawdown = 0.0
    minimum_drawdown_buffer = math.inf
    eod_rule = rules.eod_drawdown
    threshold = float(eod_rule.initial_threshold) if eod_rule else -math.inf
    highest_eod_balance = balance
    account_closed = False
    closure_reason = ""
    daily_loss_lock_count = 0
    position_rejection_count = 0
    payout_count = 0
    gross_payouts = 0.0
    first_payout_session: int | None = None
    qualifying_profit_days = 0
    payout_cycle_profit = 0.0
    payout_cycle_best_day = 0.0
    target_reached = False
    target_session: int | None = None
    position_close_violation_count = 0
    events: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []

    grouped = list(normalized.groupby("session_date", sort=True))
    for session_number, (session_date, session_trades) in enumerate(grouped, start=1):
        if account_closed or payout_count >= int(getattr(rules.payouts, "maximum_payouts", 10**9)):
            break
        if rules.evaluation:
            access_end = start + timedelta(days=rules.evaluation.access_period_calendar_days - 1)
            if session_date > access_end:
                account_closed = True
                closure_reason = "evaluation_access_period_expired"
                events.append(
                    {
                        "session_date": session_date.isoformat(),
                        "event": "account_closed",
                        "reason": closure_reason,
                        "balance": balance,
                        "eod_threshold": threshold,
                    }
                )
                break
        session_start_balance = balance
        session_pnl = 0.0
        profit_before_session = balance - starting_balance
        tier = _active_tier(profile, profit_before_session)
        maximum_contracts = tier.maximum_contracts if tier else int(rules.fixed_maximum_contracts or 0)
        daily_loss_limit = tier.daily_loss_limit if tier else float(rules.fixed_daily_loss_limit or math.inf)
        session_locked = False

        for _, trade in session_trades.iterrows():
            if session_locked or account_closed:
                break
            close_compliant = _position_close_compliant(trade, profile)
            assert close_compliant is not None
            if not close_compliant:
                position_close_violation_count += 1
                events.append(
                    _event(
                        session_date,
                        trade,
                        "position_close_deadline_violation",
                        balance,
                        threshold,
                        deadline=rules.position_close_deadline,
                    )
                )
            contracts = int(trade["contracts"])
            if contracts > maximum_contracts:
                position_rejection_count += 1
                events.append(
                    _event(
                        session_date,
                        trade,
                        "position_size_rejected",
                        balance,
                        threshold,
                        maximum_contracts=maximum_contracts,
                        requested_contracts=contracts,
                    )
                )
                continue

            worst_equity = _intratrade_min_equity(trade, balance)
            assert worst_equity is not None
            peak_equity = max(peak_equity, balance)
            max_drawdown = max(max_drawdown, peak_equity - float(worst_equity))
            if eod_rule:
                minimum_drawdown_buffer = min(minimum_drawdown_buffer, float(worst_equity) - threshold)
                if float(worst_equity) <= threshold:
                    account_closed = True
                    closure_reason = "eod_drawdown_threshold"
                    events.append(
                        _event(session_date, trade, "account_closed", worst_equity, threshold, reason=closure_reason)
                    )
                    break

            intraday_loss = float(worst_equity) - session_start_balance
            if intraday_loss <= -daily_loss_limit:
                daily_loss_lock_count += 1
                session_locked = True
                # A DLL event liquidates the position. Preserve that adverse
                # equity as the next account state instead of erasing the loss.
                balance = float(worst_equity)
                session_pnl = balance - session_start_balance
                events.append(
                    _event(
                        session_date,
                        trade,
                        "daily_loss_lock",
                        worst_equity,
                        threshold,
                        daily_loss_limit=daily_loss_limit,
                    )
                )
                break

            pnl = float(trade["net_pnl"])
            balance += pnl
            session_pnl += pnl
            peak_equity = max(peak_equity, balance)
            max_drawdown = max(max_drawdown, peak_equity - balance)
            if eod_rule:
                minimum_drawdown_buffer = min(minimum_drawdown_buffer, balance - threshold)
                if balance <= threshold:
                    account_closed = True
                    closure_reason = "eod_drawdown_threshold"
                    events.append(_event(session_date, trade, "account_closed", balance, threshold, reason=closure_reason))
                    break
            events.append(_event(session_date, trade, "trade_closed", balance, threshold, net_pnl=pnl))

        if account_closed:
            break

        highest_eod_balance = max(highest_eod_balance, balance)
        if eod_rule:
            candidate = highest_eod_balance - float(eod_rule.amount)
            if eod_rule.locked_threshold is not None:
                candidate = min(candidate, float(eod_rule.locked_threshold))
            threshold = max(threshold, candidate)
            minimum_drawdown_buffer = min(minimum_drawdown_buffer, balance - threshold)

        payout_cycle_profit += session_pnl
        payout_cycle_best_day = max(payout_cycle_best_day, session_pnl if session_pnl > 0 else 0.0)
        payout = 0.0
        if rules.payouts:
            payout_rules = rules.payouts
            if session_pnl >= payout_rules.minimum_daily_profit:
                qualifying_profit_days += 1
            consistency = (
                payout_cycle_best_day / payout_cycle_profit if payout_cycle_profit > 0 else math.inf
            )
            eligible = (
                qualifying_profit_days >= payout_rules.qualifying_profit_days
                and balance >= payout_rules.minimum_request_balance
                and consistency < payout_rules.consistency_limit
                and payout_count < payout_rules.maximum_payouts
            )
            if eligible:
                available = max(0.0, balance - payout_rules.safety_net_balance)
                request = min(float(payout_rules.payout_caps[payout_count]), available)
                if request >= payout_rules.minimum_payout:
                    payout = request
                    balance -= request
                    payout_count += 1
                    gross_payouts += request * payout_rules.payout_profit_share
                    if first_payout_session is None:
                        first_payout_session = session_number
                    qualifying_profit_days = 0
                    payout_cycle_profit = 0.0
                    payout_cycle_best_day = 0.0
                    events.append(
                        {
                            "session_date": session_date.isoformat(),
                            "event": "payout",
                            "balance": balance,
                            "eod_threshold": threshold,
                            "payout": payout,
                            "payout_number": payout_count,
                        }
                    )

        if rules.evaluation and balance >= starting_balance + rules.evaluation.profit_target:
            target_reached = True
            target_session = session_number

        daily_rows.append(
            {
                "session_date": session_date.isoformat(),
                "session_number": session_number,
                "starting_balance": session_start_balance,
                "net_pnl": session_pnl,
                "ending_balance_before_payout": balance + payout,
                "payout": payout,
                "ending_balance": balance,
                "eod_threshold": threshold if eod_rule else None,
                "drawdown_buffer": balance - threshold if eod_rule else None,
                "maximum_contracts": maximum_contracts,
                "daily_loss_limit": daily_loss_limit,
                "qualifying_profit_days": qualifying_profit_days,
                "payout_cycle_profit": payout_cycle_profit,
                "payout_cycle_best_day": payout_cycle_best_day,
            }
        )
        if target_reached:
            break

    inactivity_breach = False
    if rules.inactivity and not account_closed:
        inactivity_breach = _inactivity_breached(daily_rows, start, end, rules.inactivity)
        if inactivity_breach:
            account_closed = True
            closure_reason = "inactivity"
            events.append(
                {
                    "session_date": end.isoformat(),
                    "event": "account_closed",
                    "reason": closure_reason,
                    "balance": balance,
                    "eod_threshold": threshold,
                }
            )

    source_sessions = int(normalized["session_date"].nunique())
    evidence_sessions = int(source_evidence_session_count or source_sessions)
    evidence_complete = evidence_sessions >= profile.evaluation_policy.minimum_horizon_sessions
    costs_total = float(costs.total) if costs is not None else 0.0
    net_after_costs = gross_payouts - costs_total
    payout_to_cost = gross_payouts / costs_total if costs_total > 0 else None
    deterministic_failures = []
    policy = profile.evaluation_policy
    if policy.deterministic_require_no_closure and account_closed:
        deterministic_failures.append(f"account closed: {closure_reason}")
    if policy.deterministic_require_no_daily_loss_lock and daily_loss_lock_count:
        deterministic_failures.append(f"daily loss locks: {daily_loss_lock_count}")
    if policy.deterministic_require_no_position_rejection and position_rejection_count:
        deterministic_failures.append(f"position-size rejections: {position_rejection_count}")
    if position_close_violation_count:
        deterministic_failures.append(f"position-close deadline violations: {position_close_violation_count}")
    if profile.identity.account_kind == "prop_challenge" and not target_reached:
        deterministic_failures.append("evaluation target was not reached")

    verdict = "FAIL" if deterministic_failures else "PASS"
    unresolved = []
    if not evidence_complete:
        unresolved.append(
            f"only {evidence_sessions} source sessions are available; "
            f"{profile.evaluation_policy.minimum_horizon_sessions} are required"
        )
    if not profile.promotable:
        unresolved.append("profile is synthetic and non-promotable")
    if unresolved:
        verdict = "NEEDS MANUAL REVIEW"

    summary = {
        "schema": "alphaquest.account-path-evaluation/v1",
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "account_kind": profile.identity.account_kind,
        "verdict": verdict,
        "deterministic_failures": deterministic_failures,
        "unresolved": unresolved,
        "source_trade_count": int(len(normalized)),
        "source_session_count": source_sessions,
        "source_evidence_session_count": evidence_sessions,
        "evaluation_start": start.isoformat(),
        "evaluation_end": end.isoformat(),
        "ending_balance": float(balance),
        "account_closed": bool(account_closed),
        "closure_reason": closure_reason or None,
        "daily_loss_lock_count": int(daily_loss_lock_count),
        "position_rejection_count": int(position_rejection_count),
        "position_close_violation_count": int(position_close_violation_count),
        "maximum_drawdown": float(max_drawdown),
        "minimum_drawdown_buffer": (
            float(minimum_drawdown_buffer) if math.isfinite(minimum_drawdown_buffer) else None
        ),
        "target_reached": bool(target_reached),
        "sessions_to_target": target_session,
        "payout_count": int(payout_count),
        "gross_payouts": float(gross_payouts),
        "sessions_to_first_payout": first_payout_session,
        "costs_included": costs is not None,
        "total_acquisition_cost": costs_total if costs is not None else None,
        "net_payout_after_costs": net_after_costs if costs is not None else None,
        "payout_to_cost_ratio": payout_to_cost,
        "inactivity_breach": bool(inactivity_breach),
    }
    return AccountPathEvaluation(summary, pd.DataFrame(events), pd.DataFrame(daily_rows))


def _normalize_trades(trades: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    issues: list[str] = []
    required = {"session_date", "net_pnl", "contracts"}
    missing = sorted(required - set(trades.columns))
    if missing:
        return pd.DataFrame(), ["trade log is missing required columns: " + ", ".join(missing)]
    frame = trades.copy().reset_index(drop=True)
    dates = pd.to_datetime(frame["session_date"], errors="coerce")
    pnl = pd.to_numeric(frame["net_pnl"], errors="coerce")
    contracts = pd.to_numeric(frame["contracts"], errors="coerce")
    if dates.isna().any():
        issues.append("trade log contains invalid session_date values")
    if pnl.isna().any() or not np.isfinite(pnl.to_numpy(dtype=float)).all():
        issues.append("trade log contains invalid net_pnl values")
    if contracts.isna().any() or (contracts < 1).any() or not np.equal(contracts, np.floor(contracts)).all():
        issues.append("trade log contracts must be positive integers")
    frame["session_date"] = dates.dt.date
    frame["net_pnl"] = pnl.astype(float)
    frame["contracts"] = contracts.fillna(0).astype(int)
    timestamp = next((name for name in ("entry_timestamp", "exit_timestamp") if name in frame.columns), None)
    if timestamp:
        parsed = pd.to_datetime(frame[timestamp], errors="coerce", utc=True)
        if parsed.isna().any():
            issues.append(f"trade log contains invalid {timestamp} values")
        frame["_account_order"] = parsed
        frame = frame.sort_values(["session_date", "_account_order"], kind="stable").reset_index(drop=True)
    return frame, issues


def _intratrade_min_equity(trade: Mapping[str, Any], balance: float) -> float | None:
    absolute = _finite_value(trade.get("intraday_min_equity"))
    if absolute is not None:
        return absolute
    relative = _finite_value(trade.get("intratrade_min_pnl"))
    if relative is not None:
        return balance + relative
    mae_currency = _finite_value(trade.get("mae_currency"))
    if mae_currency is not None:
        return balance - abs(mae_currency)
    excursion = _finite_value(trade.get("max_adverse_excursion"))
    point_value = _finite_value(trade.get("point_value"))
    contracts = _finite_value(trade.get("contracts"))
    if excursion is not None and point_value is not None and contracts is not None:
        return balance - abs(excursion) * point_value * contracts
    return None


def _position_close_compliant(
    trade: Mapping[str, Any],
    profile: AccountRuleProfileV1,
) -> bool | None:
    declared = trade.get("forced_flatten_compliant")
    if declared is not None and not pd.isna(declared):
        if isinstance(declared, (bool, np.bool_)):
            return bool(declared)
        if str(declared).strip().lower() in {"true", "1", "yes"}:
            return True
        if str(declared).strip().lower() in {"false", "0", "no"}:
            return False
        return None
    raw_exit = trade.get("exit_timestamp")
    if raw_exit is None or pd.isna(raw_exit):
        return None
    parsed = pd.to_datetime(raw_exit, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    local = parsed.tz_convert(profile.identity.timezone)
    return local.strftime("%H:%M:%S") <= profile.rules.position_close_deadline


def _active_tier(profile: AccountRuleProfileV1, profit: float) -> ScalingTierV1 | None:
    for tier in profile.rules.scaling_tiers:
        if profit < tier.minimum_profit:
            continue
        if tier.maximum_profit_exclusive is None or profit < tier.maximum_profit_exclusive:
            return tier
    return profile.rules.scaling_tiers[-1] if profile.rules.scaling_tiers else None


def _inactivity_breached(daily_rows: list[dict[str, Any]], start: date, end: date, rule) -> bool:
    pnl_by_date = {date.fromisoformat(row["session_date"]): float(row["net_pnl"]) for row in daily_rows}
    current = start + timedelta(days=rule.rolling_calendar_days - 1)
    while current <= end:
        window_start = current - timedelta(days=rule.rolling_calendar_days - 1)
        qualifying = sum(
            1
            for session_date, pnl in pnl_by_date.items()
            if window_start <= session_date <= current and pnl >= rule.minimum_daily_profit
        )
        if qualifying < rule.required_profit_days:
            return True
        current += timedelta(days=1)
    return False


def _event(session_date: date, trade: Mapping[str, Any], event: str, balance: float, threshold: float, **extra):
    return {
        "session_date": session_date.isoformat(),
        "trade_id": trade.get("trade_id"),
        "event": event,
        "balance": float(balance),
        "eod_threshold": float(threshold) if math.isfinite(threshold) else None,
        **extra,
    }


def _empty_summary(profile: AccountRuleProfileV1, issues: list[str]) -> dict[str, Any]:
    return {
        "schema": "alphaquest.account-path-evaluation/v1",
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "account_kind": profile.identity.account_kind,
        "verdict": "NEEDS MANUAL REVIEW",
        "deterministic_failures": [],
        "unresolved": issues,
        "source_trade_count": 0,
        "source_session_count": 0,
    }


def _finite_value(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _coerce_date(value: date | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


__all__ = ["AccountPathEvaluation", "evaluate_account_trade_path"]
