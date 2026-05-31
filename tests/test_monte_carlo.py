from propstack.backtest.engine import BacktestEngine
from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.prop.rules import PropRules
from propstack.prop.simulator import simulate_prop_path
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
