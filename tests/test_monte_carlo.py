from propstack.backtest.engine import BacktestEngine
from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.prop.rules import PropRules
from propstack.prop.simulator import simulate_prop_path, simulate_prop_path_with_events
import propstack.research.monte_carlo as monte_carlo_module
from propstack.research.monte_carlo import run_monte_carlo, run_monte_carlo_with_audit
from propstack.run_monte_carlo import load_monte_carlo_trade_source
from tests.test_backtest_engine import BASE_CFG
from tests.test_data_pipeline import DATA_CFG
import pandas as pd
import pytest


def _trades():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    return BacktestEngine(BASE_CFG).run(data)["trades"]


def test_monte_carlo_prop_rule_breach():
    trades = _trades()
    rules = PropRules(starting_balance=50000, daily_loss_limit=1, trailing_drawdown=10)
    result = simulate_prop_path(trades, rules)
    assert "account_breached" in result


def test_payout_eligible_when_threshold_reached_before_drawdown_limit():
    trades = pd.DataFrame(
        [
            {"session_date": "2024-01-02", "contracts": 1, "net_pnl": 1200.0},
            {"session_date": "2024-01-03", "contracts": 1, "net_pnl": -2500.0},
        ]
    )

    result = simulate_prop_path(
        trades,
        PropRules(
            starting_balance=50000,
            payout_threshold=1000,
            drawdown_limit_pct=0.03,
            trailing_drawdown=100000,
            daily_loss_limit=100000,
        ),
    )

    assert result["payout_eligible"] is True


def test_payout_not_eligible_when_drawdown_limit_reached_before_threshold():
    trades = pd.DataFrame(
        [
            {"session_date": "2024-01-02", "contracts": 1, "net_pnl": -1600.0},
            {"session_date": "2024-01-03", "contracts": 1, "net_pnl": 3000.0},
        ]
    )

    result = simulate_prop_path(
        trades,
        PropRules(
            starting_balance=50000,
            payout_threshold=1000,
            drawdown_limit_pct=0.03,
            trailing_drawdown=100000,
            daily_loss_limit=100000,
        ),
    )

    assert result["payout_eligible"] is False


def test_absolute_profit_target_and_drawdown_limit_override_percent_rules():
    trades = pd.DataFrame(
        [
            {"session_date": "2024-01-02", "contracts": 1, "net_pnl": 49000.0},
            {"session_date": "2024-01-03", "contracts": 1, "net_pnl": 1000.0},
        ]
    )

    result = simulate_prop_path(
        trades,
        PropRules(
            starting_balance=100000,
            profit_target_pct=0.01,
            drawdown_limit_pct=0.99,
            profit_target_amount=50000,
            drawdown_limit_amount=10000,
            trailing_drawdown=100000,
            daily_loss_limit=100000,
        ),
    )

    assert result["profit_before_drawdown"] is True

    drawdown_first = simulate_prop_path(
        pd.DataFrame([{"session_date": "2024-01-02", "contracts": 1, "net_pnl": -10000.0}]),
        PropRules(
            starting_balance=100000,
            profit_target_pct=0.01,
            drawdown_limit_pct=0.99,
            profit_target_amount=50000,
            drawdown_limit_amount=10000,
            trailing_drawdown=100000,
            daily_loss_limit=100000,
        ),
    )

    assert drawdown_first["drawdown_before_profit"] is True


def test_max_contracts_caps_contract_count_instead_of_breaching():
    trades = pd.DataFrame(
        [
            {"trade_id": 10, "session_date": "2024-01-02", "contracts": 10, "net_pnl": 1000.0},
        ]
    )

    result, events = simulate_prop_path_with_events(
        trades,
        PropRules(
            starting_balance=50000,
            max_contracts=5,
            trailing_drawdown=100000,
            daily_loss_limit=100000,
        ),
    )

    assert result["account_breached"] is False
    assert result["breach_reason"] == ""
    assert result["net_pnl"] == 500.0
    assert events[0]["sim_contracts"] == 5
    assert events[0]["sim_net_pnl"] == 500.0
    assert "max_contracts_capped" in events[0]["event"]


def test_prop_lifecycle_challenge_requires_target_and_consistency():
    trades = pd.DataFrame(
        [
            {"trade_id": 1, "session_date": "2024-01-02", "contracts": 1, "net_pnl": 2000.0},
            {"trade_id": 2, "session_date": "2024-01-03", "contracts": 1, "net_pnl": 1000.0},
            {"trade_id": 3, "session_date": "2024-01-04", "contracts": 1, "net_pnl": 1000.0},
        ]
    )

    result, events = simulate_prop_path_with_events(
        trades,
        PropRules(
            account_lifecycle_enabled=True,
            starting_balance=50000,
            trailing_drawdown=2000,
            challenge_fee=98,
            challenge_profit_target_amount=3000,
            challenge_consistency_limit=0.50,
            trailing_drawdown_lock_balance=52100,
            trailing_drawdown_locked_floor=50100,
            daily_loss_limit=100000,
        ),
    )

    assert result["challenge_passes"] == 1
    assert result["profit_before_drawdown"] is True
    assert result["total_challenge_fees"] == 98.0
    assert result["net_pnl"] == -98.0
    trade_events = [row for row in events if str(row["event"]).startswith("trade")]
    assert "challenge_passed" not in trade_events[1]["event"]
    assert "challenge_passed" in trade_events[2]["event"]
    assert trade_events[2]["challenge_consistency_ratio"] == 0.5


def test_prop_lifecycle_replacement_fee_after_breach_ignores_account_loss():
    trades = pd.DataFrame(
        [
            {"trade_id": 1, "session_date": "2024-01-02", "contracts": 1, "net_pnl": -2100.0},
            {"trade_id": 2, "session_date": "2024-01-03", "contracts": 1, "net_pnl": 1500.0},
            {"trade_id": 3, "session_date": "2024-01-04", "contracts": 1, "net_pnl": 1500.0},
        ]
    )

    result = simulate_prop_path(
        trades,
        PropRules(
            account_lifecycle_enabled=True,
            starting_balance=50000,
            trailing_drawdown=2000,
            challenge_fee=98,
            challenge_profit_target_amount=3000,
            challenge_consistency_limit=0.50,
            daily_loss_limit=100000,
        ),
    )

    assert result["accounts_purchased"] == 2
    assert result["accounts_breached"] == 1
    assert result["challenge_passes"] == 1
    assert result["total_challenge_fees"] == 196.0
    assert result["net_pnl"] == -196.0


def test_prop_lifecycle_funded_payout_uses_profit_share_and_resets_profit_days():
    trades = pd.DataFrame(
        [
            {"trade_id": 1, "session_date": "2024-01-02", "contracts": 1, "net_pnl": 1500.0},
            {"trade_id": 2, "session_date": "2024-01-03", "contracts": 1, "net_pnl": 1500.0},
            {"trade_id": 3, "session_date": "2024-01-04", "contracts": 1, "net_pnl": 400.0},
            {"trade_id": 4, "session_date": "2024-01-05", "contracts": 1, "net_pnl": 400.0},
            {"trade_id": 5, "session_date": "2024-01-08", "contracts": 1, "net_pnl": 400.0},
            {"trade_id": 6, "session_date": "2024-01-09", "contracts": 1, "net_pnl": 400.0},
            {"trade_id": 7, "session_date": "2024-01-10", "contracts": 1, "net_pnl": 400.0},
        ]
    )

    result, events = simulate_prop_path_with_events(
        trades,
        PropRules(
            account_lifecycle_enabled=True,
            starting_balance=50000,
            trailing_drawdown=2000,
            challenge_fee=98,
            challenge_profit_target_amount=3000,
            challenge_consistency_limit=0.50,
            funded_starting_balance=50000,
            funded_payout_min_profit_day=150,
            funded_payout_required_profit_days=5,
            funded_payout_profit_fraction=0.50,
            funded_payout_profit_share=0.90,
            funded_payout_max_amount=2000,
            daily_loss_limit=100000,
        ),
    )

    assert result["payout_count"] == 1
    assert result["gross_payouts"] == 1000.0
    assert result["net_payouts"] == 900.0
    assert result["net_pnl"] == 802.0
    payout_events = [row for row in events if "funded_payout" in str(row["event"])]
    assert len(payout_events) == 1
    assert payout_events[0]["payout_request"] == 1000.0
    assert payout_events[0]["payout_net"] == 900.0
    assert payout_events[0]["funded_profit_days"] == 0


def test_prop_lifecycle_eod_trailing_drawdown_locks_at_configured_floor():
    trades = pd.DataFrame(
        [
            {"trade_id": 1, "session_date": "2024-01-02", "contracts": 1, "net_pnl": 2100.0},
            {"trade_id": 2, "session_date": "2024-01-03", "contracts": 1, "net_pnl": -1999.0},
            {"trade_id": 3, "session_date": "2024-01-04", "contracts": 1, "net_pnl": -2.0},
        ]
    )

    result, events = simulate_prop_path_with_events(
        trades,
        PropRules(
            account_lifecycle_enabled=True,
            starting_balance=50000,
            trailing_drawdown=2000,
            challenge_profit_target_amount=99999,
            trailing_drawdown_lock_balance=52100,
            trailing_drawdown_locked_floor=50100,
            daily_loss_limit=100000,
        ),
    )

    assert result["accounts_breached"] == 1
    eod_events = [row for row in events if str(row["event"]).startswith("eod_update")]
    assert eod_events[0]["trailing_floor"] == 50100.0
    breach_events = [row for row in events if "trailing_drawdown_breach" in str(row["event"])]
    assert breach_events[0]["balance"] == 50099.0


def test_monte_carlo_summary():
    trades = _trades()
    results, summary = run_monte_carlo(trades, {"runs": 5, "seed": 1}, PropRules())
    assert len(results) == 5
    assert "probability_account_breach" in summary
    assert summary["mean_net_pnl"] == summary["average_net_pnl"]
    assert summary["sampling"] == {
        "seed": 1,
        "skip_trade_probability": 0.0,
        "skip_winning_trade_probability": 0.0,
        "cluster_losses": False,
    }


def test_lifecycle_monte_carlo_benchmark_uses_strict_positive_mean_net_pnl():
    trades = pd.DataFrame(
        [
            {"trade_id": 1, "session_date": "2024-01-02", "contracts": 1, "net_pnl": 0.0},
        ]
    )

    _, summary = run_monte_carlo(
        trades,
        {"runs": 1, "seed": 1},
        PropRules(account_lifecycle_enabled=True, challenge_fee=0.0),
    )

    assert summary["mean_net_pnl"] == 0.0
    assert summary["prop_pass_chance_benchmark_metric"] == "mean_net_pnl"
    assert summary["prop_pass_chance_benchmark_threshold"] == 0.0
    assert summary["meets_prop_pass_chance_benchmark"] is False


def test_monte_carlo_audit_logs_path_trades_and_events():
    trades = pd.DataFrame(
        [
            {"trade_id": 10, "session_date": "2024-01-02", "contracts": 1, "net_pnl": 1200.0},
        ]
    )

    results, _, path_trades, path_events = run_monte_carlo_with_audit(
        trades,
        {"runs": 1, "seed": 1, "retain_path_trades": True, "retain_path_events": True},
        PropRules(
            starting_balance=50000,
            payout_threshold=1000,
            trailing_drawdown=100000,
            daily_loss_limit=100000,
        ),
    )

    assert bool(results.loc[0, "payout_eligible"]) is True
    assert len(path_trades) == 1
    assert path_trades.loc[0, "run_id"] == 1
    assert path_trades.loc[0, "sample_index"] == 1
    assert path_trades.loc[0, "path_index"] == 1
    assert path_trades.loc[0, "source_trade_id"] == 10
    assert path_trades.loc[0, "source_net_pnl"] == 1200.0
    assert path_trades.loc[0, "sim_net_pnl"] == 1200.0
    assert bool(path_trades.loc[0, "was_skipped"]) is False
    assert len(path_events) == 1
    assert path_events.loc[0, "run_id"] == 1
    assert path_events.loc[0, "source_trade_id"] == 10
    assert "payout_threshold_reached" in path_events.loc[0, "event"]


def test_monte_carlo_audit_logs_skipped_trades():
    trades = pd.DataFrame(
        [
            {"trade_id": 10, "session_date": "2024-01-02", "contracts": 1, "net_pnl": 1200.0},
            {"trade_id": 11, "session_date": "2024-01-03", "contracts": 1, "net_pnl": -500.0},
        ]
    )

    results, _, path_trades, path_events = run_monte_carlo_with_audit(
        trades,
        {
            "runs": 1,
            "seed": 1,
            "skip_trade_probability": 1.0,
            "retain_path_trades": True,
            "retain_path_events": True,
        },
        PropRules(),
    )

    assert results.loc[0, "net_pnl"] == 0.0
    assert len(path_trades) == 2
    assert path_trades["was_skipped"].tolist() == [True, True]
    assert path_trades["skip_reason"].tolist() == ["skip_trade_probability", "skip_trade_probability"]
    assert path_trades["path_index"].isna().all()
    assert path_trades["sim_net_pnl"].isna().all()
    assert path_events.empty


def test_monte_carlo_resizes_risk_percent_trades_from_path_net_liq():
    trades = pd.DataFrame(
        [
            {
                "trade_id": 10,
                "session_date": "2024-01-02",
                "contracts": 4,
                "risk_points": 5.0,
                "position_sizing_mode": "risk_percent_net_liq",
                "net_pnl": -4000.0,
            },
            {
                "trade_id": 11,
                "session_date": "2024-01-03",
                "contracts": 4,
                "risk_points": 5.0,
                "position_sizing_mode": "risk_percent_net_liq",
                "net_pnl": -4000.0,
            },
        ]
    )

    results, _, path_trades, path_events = run_monte_carlo_with_audit(
        trades,
        {
            "runs": 1,
            "seed": 1,
            "retain_path_trades": True,
            "retain_path_events": True,
            "_core": {
                "initial_balance": 100000,
                "tick_size": 0.25,
                "tick_value": 12.5,
                "position_sizing": {
                    "mode": "risk_percent_net_liq",
                    "risk_pct": 0.01,
                    "rounding": "floor",
                    "min_contracts": 1,
                },
            },
        },
        PropRules(starting_balance=50000, trailing_drawdown=100000, daily_loss_limit=100000),
    )

    applied = path_trades.sort_values("path_index").reset_index(drop=True)
    assert applied["source_contracts"].tolist() == [4, 4]
    assert applied["sim_contracts"].tolist() == [2, 1]
    assert applied["source_net_pnl"].tolist() == [-4000.0, -4000.0]
    assert applied["sim_net_pnl"].tolist() == [-2000.0, -1000.0]
    assert results.loc[0, "net_pnl"] == -3000.0
    assert path_events.sort_values("path_index")["sim_contracts"].tolist() == [2, 1]


def test_monte_carlo_fixed_contract_override_resizes_all_source_trades():
    trades = pd.DataFrame(
        [
            {
                "trade_id": 10,
                "session_date": "2024-01-02",
                "contracts": 4,
                "risk_points": 5.0,
                "position_sizing_mode": "risk_percent_net_liq",
                "net_pnl": -4000.0,
            },
        ]
    )

    results, _, path_trades, path_events = run_monte_carlo_with_audit(
        trades,
        {
            "runs": 1,
            "seed": 1,
            "retain_path_trades": True,
            "retain_path_events": True,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 2},
        },
        PropRules(starting_balance=50000, trailing_drawdown=100000, daily_loss_limit=100000),
    )

    assert results.loc[0, "net_pnl"] == -2000.0
    assert path_trades.loc[0, "source_contracts"] == 4
    assert path_trades.loc[0, "sim_contracts"] == 2
    assert path_trades.loc[0, "source_net_pnl"] == -4000.0
    assert path_trades.loc[0, "sim_net_pnl"] == -2000.0
    assert path_trades.loc[0, "position_sizing_mode"] == "fixed_contracts"
    assert pd.isna(path_trades.loc[0, "position_sizing_net_liq"])
    assert path_events.loc[0, "sim_contracts"] == 2


def test_monte_carlo_caps_override_contracts_at_prop_rule_max():
    trades = pd.DataFrame(
        [
            {
                "trade_id": 10,
                "session_date": "2024-01-02",
                "contracts": 3,
                "net_pnl": 900.0,
            },
        ]
    )

    results, _, path_trades, path_events = run_monte_carlo_with_audit(
        trades,
        {
            "runs": 1,
            "seed": 1,
            "retain_path_trades": True,
            "retain_path_events": True,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 6},
        },
        PropRules(
            starting_balance=50000,
            max_contracts=2,
            trailing_drawdown=100000,
            daily_loss_limit=100000,
        ),
    )

    assert bool(results.loc[0, "account_breached"]) is False
    assert results.loc[0, "breach_reason"] == ""
    assert results.loc[0, "net_pnl"] == 600.0
    assert path_trades.loc[0, "source_contracts"] == 3
    assert path_trades.loc[0, "sim_contracts"] == 2
    assert path_trades.loc[0, "sim_net_pnl"] == 600.0
    assert bool(path_trades.loc[0, "was_applied"]) is True
    assert path_events.loc[0, "sim_contracts"] == 2
    assert "max_contracts_capped" in path_events.loc[0, "event"]


def test_monte_carlo_current_net_liq_override_resizes_all_source_trades():
    trades = pd.DataFrame(
        [
            {
                "trade_id": 10,
                "session_date": "2024-01-02",
                "contracts": 4,
                "risk_points": 5.0,
                "position_sizing_mode": "fixed_contracts",
                "net_pnl": -4000.0,
            },
            {
                "trade_id": 11,
                "session_date": "2024-01-03",
                "contracts": 4,
                "risk_points": 5.0,
                "position_sizing_mode": "fixed_contracts",
                "net_pnl": -4000.0,
            },
        ]
    )

    results, _, path_trades, _ = run_monte_carlo_with_audit(
        trades,
        {
            "runs": 1,
            "seed": 1,
            "retain_path_trades": True,
            "retain_path_events": True,
            "position_sizing": {
                "mode": "risk_percent_net_liq",
                "risk_pct": 0.01,
                "rounding": "floor",
                "min_contracts": 1,
            },
            "_core": {
                "tick_size": 0.25,
                "tick_value": 12.5,
                "position_sizing": {"mode": "fixed_contracts", "contracts": 4},
            },
        },
        PropRules(starting_balance=50000, trailing_drawdown=100000, daily_loss_limit=100000),
    )

    applied = path_trades.sort_values("path_index").reset_index(drop=True)
    assert applied["sim_contracts"].tolist() == [2, 1]
    assert applied["sim_net_pnl"].tolist() == [-2000.0, -1000.0]
    assert applied["position_sizing_mode"].tolist() == ["risk_percent_net_liq", "risk_percent_net_liq"]
    assert applied["position_sizing_net_liq"].tolist() == [50000.0, 48000.0]
    assert results.loc[0, "net_pnl"] == -3000.0


def test_monte_carlo_initial_net_liq_override_uses_starting_balance_each_trade():
    trades = pd.DataFrame(
        [
            {
                "trade_id": 10,
                "session_date": "2024-01-02",
                "contracts": 4,
                "risk_points": 5.0,
                "position_sizing_mode": "fixed_contracts",
                "net_pnl": -4000.0,
            },
            {
                "trade_id": 11,
                "session_date": "2024-01-03",
                "contracts": 4,
                "risk_points": 5.0,
                "position_sizing_mode": "fixed_contracts",
                "net_pnl": -4000.0,
            },
        ]
    )

    results, _, path_trades, _ = run_monte_carlo_with_audit(
        trades,
        {
            "runs": 1,
            "seed": 1,
            "retain_path_trades": True,
            "retain_path_events": True,
            "position_sizing": {
                "mode": "risk_percent_initial_balance",
                "risk_pct": 0.01,
                "rounding": "floor",
                "min_contracts": 1,
            },
            "_core": {
                "tick_size": 0.25,
                "tick_value": 12.5,
                "position_sizing": {"mode": "fixed_contracts", "contracts": 4},
            },
        },
        PropRules(starting_balance=50000, trailing_drawdown=100000, daily_loss_limit=100000),
    )

    applied = path_trades.sort_values("path_index").reset_index(drop=True)
    assert applied["sim_contracts"].tolist() == [2, 2]
    assert applied["sim_net_pnl"].tolist() == [-2000.0, -2000.0]
    assert applied["position_sizing_mode"].tolist() == [
        "risk_percent_initial_balance",
        "risk_percent_initial_balance",
    ]
    assert applied["position_sizing_net_liq"].tolist() == [50000.0, 50000.0]
    assert results.loc[0, "net_pnl"] == -4000.0


def test_monte_carlo_parallel_branch_is_configurable(monkeypatch):
    trades = _trades()
    calls = []

    def fake_run_parallel_monte_carlo(trades, cfg, rules, total_runs, workers):
        calls.append({"total_runs": total_runs, "workers": workers})
        return [
            monte_carlo_module._evaluate_monte_carlo_run(run_id, trades, cfg, rules)
            for run_id in range(1, total_runs + 1)
        ]

    monkeypatch.setattr(monte_carlo_module.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(monte_carlo_module, "_run_parallel_monte_carlo", fake_run_parallel_monte_carlo)

    results, summary = run_monte_carlo(
        trades,
        {"runs": 5, "seed": 1, "parallel": {"enabled": True, "workers": 2, "scope": "runs"}},
        PropRules(),
    )

    assert len(results) == 5
    assert calls == [{"total_runs": 5, "workers": 2}]
    assert summary["parallel"] == {"enabled": True, "workers": 2, "scope": "runs"}


def test_monte_carlo_loads_variant_wfa_oos_trade_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    campaign = {
        "campaign_id": "sample_campaign",
        "variant_id": "baseline",
        "dataset_id": "1m_full_history",
        "timeframe": "5m",
        "data": {"symbol": "ES", "dataset_id": "1m_full_history"},
    }
    trade_log = (
        tmp_path
        / "backtest-campaigns/sample_campaign/baseline/ES/run1/wfa/wfa_oos_trade_log.csv"
    )
    trade_log.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "trade_id": 1,
                "wfa_window_id": 1,
                "session_date": "2024-01-02",
                "contracts": 1,
                "net_pnl": 100.0,
            }
        ]
    ).to_csv(trade_log, index=False)

    trades, _, source = load_monte_carlo_trade_source(
        campaign,
        {"trade_source": "wfa_oos"},
        tmp_path / "backtest-campaigns/sample_campaign/baseline/ES/run1/monte_carlo",
        skip_validation=True,
    )

    assert len(trades) == 1
    assert trades.loc[0, "net_pnl"] == 100.0
    assert source == {"type": "wfa_oos", "path": str(trade_log.relative_to(tmp_path))}


def test_monte_carlo_loads_variant_core_trade_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    campaign = {
        "campaign_id": "sample_campaign",
        "variant_id": "baseline",
        "dataset_id": "1m_full_history",
        "timeframe": "5m",
        "data": {"symbol": "ES", "dataset_id": "1m_full_history"},
    }
    trade_log = (
        tmp_path
        / "backtest-campaigns/sample_campaign/baseline/ES/run1/core/trade_log.csv"
    )
    trade_log.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "trade_id": 1,
                "session_date": "2024-01-02",
                "contracts": 1,
                "net_pnl": 100.0,
            }
        ]
    ).to_csv(trade_log, index=False)

    trades, _, source = load_monte_carlo_trade_source(
        campaign,
        {"trade_source": "core"},
        tmp_path / "backtest-campaigns/sample_campaign/baseline/ES/run1/monte_carlo",
        skip_validation=True,
    )

    assert len(trades) == 1
    assert trades.loc[0, "net_pnl"] == 100.0
    assert source == {"type": "core", "path": str(trade_log.relative_to(tmp_path))}


def test_monte_carlo_requires_explicit_report_trade_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    campaign = {
        "campaign_id": "sample_campaign",
        "variant_id": "baseline",
        "dataset_id": "1m_full_history",
        "timeframe": "5m",
        "data": {"symbol": "ES", "dataset_id": "1m_full_history"},
    }

    with pytest.raises(ValueError, match="trade_source is required"):
        load_monte_carlo_trade_source(
            campaign,
            {},
            tmp_path / "backtest-campaigns/sample_campaign/baseline/ES/run1/monte_carlo",
            skip_validation=True,
        )


def test_monte_carlo_rejects_generic_trade_log_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    campaign = {
        "campaign_id": "sample_campaign",
        "variant_id": "baseline",
        "dataset_id": "1m_full_history",
        "timeframe": "5m",
        "data": {"symbol": "ES", "dataset_id": "1m_full_history"},
    }

    with pytest.raises(ValueError, match="trade_log is no longer supported"):
        load_monte_carlo_trade_source(
            campaign,
            {"trade_log": "some/path.csv"},
            tmp_path / "backtest-campaigns/sample_campaign/baseline/ES/run1/monte_carlo",
            skip_validation=True,
        )
