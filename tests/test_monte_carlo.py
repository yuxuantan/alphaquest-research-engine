from propstack.backtest.engine import BacktestEngine
from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.prop.rules import PropRules
from propstack.prop.simulator import simulate_prop_path
import propstack.research.monte_carlo as monte_carlo_module
from propstack.research.monte_carlo import run_monte_carlo
from tests.test_backtest_engine import BASE_CFG
from tests.test_data_pipeline import DATA_CFG


def _trades():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    return BacktestEngine(BASE_CFG).run(data)["trades"]


def test_monte_carlo_prop_rule_breach():
    trades = _trades()
    rules = PropRules(starting_balance=50000, daily_loss_limit=1, trailing_drawdown=10)
    result = simulate_prop_path(trades, rules)
    assert "account_breached" in result


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
