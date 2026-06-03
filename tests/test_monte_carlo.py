from propstack.backtest.engine import BacktestEngine
from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.prop.rules import PropRules
from propstack.prop.simulator import simulate_prop_path
import propstack.research.monte_carlo as monte_carlo_module
from propstack.research.monte_carlo import run_monte_carlo
from propstack.run_monte_carlo import load_monte_carlo_trade_source
from tests.test_backtest_engine import BASE_CFG
from tests.test_data_pipeline import DATA_CFG
import pandas as pd


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


def test_monte_carlo_summary():
    trades = _trades()
    results, summary = run_monte_carlo(trades, {"runs": 5, "seed": 1}, PropRules())
    assert len(results) == 5
    assert "probability_account_breach" in summary


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
        "data": {"symbol": "ES", "dataset_id": "1m_full_history"},
    }
    trade_log = (
        tmp_path
        / "data/reports/campaigns/sample_campaign/ES/1m_full_history/baseline/wfa/wfa_oos_trade_log.csv"
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
        tmp_path / "data/reports/campaigns/sample_campaign/ES/1m_full_history/baseline/monte_carlo",
        skip_validation=True,
    )

    assert len(trades) == 1
    assert trades.loc[0, "net_pnl"] == 100.0
    assert source == {"type": "wfa_oos", "path": str(trade_log.relative_to(tmp_path))}
